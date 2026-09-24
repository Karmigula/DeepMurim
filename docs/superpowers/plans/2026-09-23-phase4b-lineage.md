# Phase 4b: Lineage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The player can die (of age, by a blade, of qi deviation, by the law) and carry on as an heir. Heirs are children from marriage, disciples, sworn siblings or sworn followers, and they inherit wealth, arts, name and enemies. Alternatively the player starts over as a newcomer in the same world, or in a new world.

**Architecture:**
- **The player is a person like any other.** Succession moves world meta `player_id` to the heir. The dead player stays in the world, buried, with full history.
- **Death reuses the existing `died` event** (flagged `player: True`), so 3a grief and inherited grudges, 3c sect membership and the 4a "dead leave their factions" rule all fire unchanged. A listener sets the player's `dying` state.
- **The death screen is a gated state in a new `LineageMixin`**, placed first among `Game`'s bases so it can refuse every other verb. Leaving for a new world or a newcomer is signalled to the `App` through `Game.exit_to`.

| Area | System | Engine | Narration |
|---|---|---|---|
| death | `mortality.py` | `LineageMixin` | `lineage_text.py` |
| heirs | `bonds.py` | `LineageMixin` | `lineage_text.py` |
| succession | `succession.py` | `LineageMixin`, `app.py` | `lineage_text.py` |
| half-strength inheritance | `lineage.py` | — | — |

**Tech Stack:** Python 3.12, SQLite (save format v2, unchanged), pygame-ce, pytest.

**Spec:** `docs/superpowers/specs/2026-09-23-phase4b-lineage-design.md` (builds on the 4a spec `docs/superpowers/specs/2026-09-23-phase4a-world-clock-design.md`).

## Global Constraints

- No schema change. New keys:
  - player data `age` (float), `lived_to`, `white_hair`, `dying`, `ancestors`, `named_heir`, `spouse_refused`;
  - kin role `sworn_sibling`;
  - fact `heir_of`.
- **Seeds.**
  - player seasons `life:player:{id}:{n}`;
  - deviation death `deviation-death:{player}:{event id}`;
  - trial `trial:{player}:{time}`;
  - proposals `propose:{player}:{npc}:{season}`;
  - the newcomer's town `newcomer:{old player}`;
  - which avengers inherit a grudge `heir-grudge:{avenger}:{heir}`.
- **Event kinds.** New kinds must not reuse an existing kind's name (`EFFECTS` holds one handler per kind). 4b deliberately reuses `died`. Its new kinds are `player_aged`, `tried`, `imprisoned`, `proposal`, `took_disciple`, `sworn_siblings`, `named_heir` and `succession`.
- **Narration.** Every new narrated event kind gets a grammar table, an outcome builder and a journal summary. `player_aged` is committed with `world.events.commit` and is quiet in the journal.
- **The death screen** accepts only its own verbs: `succeed`, `newcomer`, `new_world`, `look` (which shows the epitaph again), `help`, `unknown`, `ambiguous`.
- Briefs keep at most 6 facts, at most 1,200 characters, and no ids.
- Test command: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`.

## Review Focus

1. **Saving and loading on the death screen.** The death screen comes back, and no other verb works. Task 1 pins this with `test_the_death_screen_survives_a_reload`.
2. **An heir who is away on sect duty (3c) or far from home.** They wake in a real town and play goes on. Task 4 pins this with `test_an_heir_away_on_duty_wakes_at_the_seat`.
3. **Dying with no one to inherit.** The screen still offers a newcomer and a new world. Task 4 pins this with `test_with_no_heir_only_a_fresh_start_is_offered`.
4. **Yielding a fight.** Yielding is never lethal, except on a capital charge. Task 2 pins this with `test_yielding_is_never_lethal_but_the_law_is`.
5. **A named heir who dies before the player.** The name is cleared, and the next candidate leads. Task 3 pins this with `test_a_dead_named_heir_is_forgotten`.

## Plan-time rulings (deviations from the spec, argued)

1. **The player's death is the existing `died` event, flagged `player: True`, not a new `player_died` kind.** Every 3a, 3c and 4a death listener then works for the player without change. *Cost if wrong:* none visible; the journal and grammar reuse `died`.
2. **The player ages when something is committed**, in `_after_commit`, not on a bare look. Every action that moves time commits something. *Cost if wrong:* none.
3. **Inherited avengers: a seeded half of the ancestor's avengers carry the grudge on**, instead of every avenger at half the chance. It gives the same expected danger, and each avenger's choice stays deterministic. *Cost if wrong:* a different spread of hunters.
4. **Only the heir's direct predecessor is looked up** for half-strength inheritance. Older ancestors come through recursion, halving again each generation. *Cost if wrong:* none; it matches "at half".
5. **An heir on sect duty (in the region, not a town) is brought back to the sect's seat** as they take up the mantle, so the player is always in a town.
6. **The existing fuzz runs gain a `keep_playing` helper.** After a death they carry on through a new world or a newcomer, instead of asserting that play never left the game screen. *Cost if wrong:* none; the rules are still checked on every turn.
7. **A dead player's masks stay theirs.** The 3a rule "every persona is the player's" becomes "the player's, or a dead person's", because rumours still name the old masks after a succession. *Cost if wrong:* none.

---

### Task 1: Mortality: aging, old age, lethal deviation, the death screen

**Files:**
- Create: `systems/mortality.py`, `engine/lineage.py`, `narrate/lineage_text.py`, `narrate/grammar/lineage.toml`
- Modify (via `.patches/4b_task1.py`):
  - `engine/game.py` (the `LineageMixin` base, `look` on the death screen, `player_aged` quiet);
  - `app.py` (following `Game.exit_to`);
  - `narrate/outcomes.py`;
  - `debug/invariants.py` (`check_lineage`; `check_sect` skips a dead founder; `check_people` knows the player's kin);
  - `tests/test_fuzz.py` (`keep_playing`).
- Test: `tests/test_mortality.py`

**Interfaces:**
- Consumes: 4a `lives.LIFESPAN`, `lives.death_chance`, `lives.current_season`, `lives.home`, `lives.SEASON`; the 3a kin `died` effect (sets `dead`, buries at the event place); `systems.bodies.load_body`; 2a `cultivation._deviation_event` (in tests).
- Produces:
  - `systems.mortality`:
    - Constants: `DEVIATION_DEATH = 0.5`, `WHITE_HAIR = 10`, `DEATH_WEIGHT = 3.0`, `CAUSES`.
    - Aging: `player_lived_to(world, player) -> int`, `lifespan(world, player) -> int`, `lifespan_near(world, player) -> bool`, `age_events(world, player) -> list[Event]`.
    - Death: `death_events(world, player, cause, killer, age=None) -> list[Event]`, `deviation_death_events(world, player, event_id) -> list[Event]`, `epitaph(world, player) -> str`.
  - Events: `player_aged` (player; data `season`, `age`, `white_hair`), and `died` with data `player: True`, `cause`, `age`. Its listener sets `dying` = `{cause, killer, place, time, age}` and writes the fact `died` or `killed` (weight 3.0).
  - `engine.lineage.LineageMixin`:
    - Constant: `DEATH_VERBS`.
    - `exit_to: str | None` (`"title"` or `"newcomer"`).
    - Death screen: `_dying()`, `_death_choices() -> list[Choice]`, `_death_lines() -> list[Line]`.
    - Hooks: `_restore`, `_special_choices`, `_special_status`, `_special_art`, `_gate`, `_after_commit`, `_before_scene`, `_status_suffix`.
    - Verb: `new_world`.
  - `debug.invariants.check_lineage(world) -> list[str]`.
  - `tests.test_fuzz.keep_playing(app, step)`.

- [ ] **Step 1: Write the failing test** — `tests/test_mortality.py`
```python
import pytest

import systems.encounters as encounters
import systems.lives as lives
import systems.mortality as mortality
from app import App
from config import Config
from engine.actions import Action
from engine.game import Game
from systems import cultivation
from systems.bodies import load_body
from systems.creation import CreationChoice


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


def texts(turn):
    return [t for t, _ in turn.lines]


def die_of_age(game, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 1.0)
    return game.perform(Action("meditate", 90))


def test_the_player_ages_with_the_seasons(game, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    game.perform(Action("meditate", 90))
    assert game.player.data["age"] == 18.25
    assert "(18)" in game.perform(Action("look")).status


def test_white_hair_warns_that_the_end_is_near(game, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    life = mortality.lifespan(game.world, game.player.id)
    game.world.update_data(game.player.id, age=life - mortality.WHITE_HAIR - 0.1)
    turn = game.perform(Action("meditate", 90))
    assert "Your hair has gone white." in texts(turn)
    assert "lifespan near" in turn.status


def test_old_age_can_kill(game, monkeypatch):
    town = game.place.id
    turn = die_of_age(game, monkeypatch)
    me = game.world.entity(game.world.get_meta("player_id"))
    assert me.data["dead"] and me.data["dying"]["cause"] == "age"
    assert game.world.targets(me.id, "buried_at") == [town]
    assert [c.action.verb for c in turn.choices][-1] == "new_world"
    assert any(t.startswith("Hero died of old age in") for t in texts(turn))
    [fact] = game.world.facts(predicate="died", subject=me.id)
    assert fact.weight == mortality.DEATH_WEIGHT


def test_the_dead_can_only_choose(game, monkeypatch):
    die_of_age(game, monkeypatch)
    assert texts(game.perform(Action("meditate", 7)))[-1] == "You are dead. Choose how your story goes on."
    assert any(t.startswith("Hero died of old age") for t in texts(game.perform(Action("look"))))


def test_qi_deviation_can_kill(game, monkeypatch):
    monkeypatch.setattr(mortality, "DEVIATION_DEATH", 1.0)
    body = load_body(game.world, game.player.id)
    events = cultivation._deviation_event(game.world, game.player.id, game.place.id, body, 100.0,
                                          list(body.meridians), "test")
    game._commit(events)
    assert game.player.data["dying"]["cause"] == "deviation"


def test_the_death_screen_survives_a_reload(tmp_path, monkeypatch):
    path = tmp_path / "dead.world"
    g = Game.new(path, "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    die_of_age(g, monkeypatch)
    g.close()
    again = Game.load(path)
    turn = again.start()
    assert [c.action.verb for c in turn.choices][-1] == "new_world" and "dead" in turn.status
    assert texts(again.perform(Action("rest", 7)))[-1] == "You are dead. Choose how your story goes on."
    again.close()


def test_a_new_world_returns_to_the_title(tmp_path, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 1.0)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new("Mortal", world_seed=11)
    app.submit("meditate season")
    assert app.state == "game" and app.choices[-1].action.verb == "new_world"
    app.submit(str(len(app.choices)))
    assert app.state == "title" and app.game is None
    app.shutdown()
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_mortality.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.mortality'`.

- [ ] **Step 3: Write mortality** — `systems/mortality.py`
```python
"""Mortality (phase 4b spec 3): the player ages with the world and can die of age, deviation, a blade or the law.

The player's death is the ordinary `died` event, flagged `player: True`, so every
death rule of 3a-4a applies to them too; a listener here opens the death screen.
"""

import systems.lives as lives
from systems.bodies import load_body
from systems.facts import make_variant, place_name, record_fact
from world.events import Event, effect, listen
from world.seed import rng_for

DEVIATION_DEATH = 0.5
WHITE_HAIR = 10          # years before the lifespan when the warning comes
DEATH_WEIGHT = 3.0
CAUSES = {"age": "of old age", "illness": "of illness", "deviation": "of qi deviation",
          "killed": "at the hands of {killer}", "executed": "under the executioner's blade"}


def player_lived_to(world, player: int) -> int:
    """The last season the player has lived; an old save's player starts living now (spec §9)."""
    found = world.entity(player).data.get("lived_to")
    if found is None:
        found = lives.current_season(world)
        world.update_data(player, lived_to=found)
    return found


def lifespan(world, player: int) -> int:
    return lives.LIFESPAN[load_body(world, player).realm]


def lifespan_near(world, player: int) -> bool:
    return float(world.entity(player).data.get("age", 18)) >= lifespan(world, player) - WHITE_HAIR


def death_events(world, player: int, cause: str, killer: int | None, age: float | None = None) -> list[Event]:
    place = lives.home(world, player)
    age = float(world.entity(player).data.get("age", 18)) if age is None else age
    return [Event("died", (killer or player, player), place, {"cause": cause, "player": True, "age": age})]


def age_events(world, player: int) -> list[Event]:
    """The player lives the seasons the world has passed; the last may be their death."""
    entity = world.entity(player)
    if entity.data.get("dead") or entity.data.get("dying"):
        return []
    done, now = player_lived_to(world, player), lives.current_season(world)
    if done >= now:
        return []
    realm = load_body(world, player).realm
    life = lives.LIFESPAN[realm]
    age = float(entity.data.get("age", 18))
    warned = bool(entity.data.get("white_hair"))
    white, died = False, None
    for n in range(done + 1, now + 1):
        age = round(age + 0.25, 2)
        if not warned and age >= life - WHITE_HAIR:
            warned = white = True
        if rng_for(world.world_seed, f"life:player:{player}:{n}").random() < lives.death_chance(age, realm):
            died = n
            break
    events = [Event("player_aged", (player,), lives.home(world, player),
                    {"season": died or now, "age": age, "white_hair": white})]
    if died is not None:
        events += death_events(world, player, "age", None, age)
    return events


def deviation_death_events(world, player: int, event_id: int) -> list[Event]:
    if rng_for(world.world_seed, f"deviation-death:{player}:{event_id}").random() < DEVIATION_DEATH:
        return death_events(world, player, "deviation", None)
    return []


def epitaph(world, player: int) -> str:
    entity = world.entity(player)
    d = entity.data.get("dying") or {}
    killer = world.entity(d["killer"]).name if d.get("killer") else "someone"
    how = CAUSES.get(d.get("cause"), "").format(killer=killer)
    where = place_name(world, d.get("place")) or "the road"
    age = int(d.get("age") or entity.data.get("age", 18))
    return f"{entity.name} died {how} in {where}, aged {age}."


@effect("player_aged")
def _aged(world, event) -> None:
    d = event.data
    changes = {"age": d["age"], "lived_to": d["season"]}
    if d["white_hair"]:
        changes["white_hair"] = True
    world.update_data(event.actors[0], **changes)


@listen("died")
def _player_died(world, event, event_id: int) -> None:
    """The player's death opens the death screen and becomes the talk of the town."""
    if not event.data.get("player"):
        return
    killer, victim = event.actors
    world.update_data(victim, dying={"cause": event.data["cause"], "killer": killer if killer != victim else None,
                                     "place": event.place, "time": world.time, "age": event.data.get("age")})
    where = place_name(world, event.place)
    if killer == victim:
        record_fact(world, victim, "died", None, place=event.place, source_event=event_id, weight=DEATH_WEIGHT,
                    variant=make_variant("died", victim, None, place=where))
    else:
        record_fact(world, killer, "killed", victim, place=event.place, source_event=event_id, weight=DEATH_WEIGHT,
                    variant=make_variant("killed", killer, victim, place=where,
                                         realm=world.entity(killer).data.get("realm")))
```

- [ ] **Step 4: Write the engine side** — `engine/lineage.py`
```python
"""Lineage in the engine (phase 4b): aging as time passes, death, and the death screen."""

import systems.mortality as mortality
from engine.actions import Action, Choice
from systems.time import format_date
from world.events import commit

DEATH_VERBS = frozenset({"succeed", "newcomer", "new_world", "look", "help", "unknown", "ambiguous"})


class LineageMixin:
    exit_to: str | None = None  # "title" or "newcomer": the App takes over (phase 4b spec 5.3)

    def _dying(self) -> dict | None:
        return self.player.data.get("dying")

    def _death_choices(self) -> list:
        return [Choice("A new world", Action("new_world"))]

    def _death_lines(self) -> list:
        self.focus, self.submenu, self.combat, self.encounter, self.challenger = None, None, None, None, None
        return [(mortality.epitaph(self.world, self.player.id), "heading"),
                ("Your story is not over. Choose how it goes on.", "system")]

    def _restore(self) -> None:
        if self._dying():
            return  # a fight or an encounter means nothing to the dead; nothing to rebuild
        super()._restore()

    def _special_choices(self):
        if self._dying():
            return self._death_choices()[:9], []
        return super()._special_choices()

    def _special_status(self):
        if self._dying():
            return f"{self.player.name} | dead | {format_date(self.world.time)}"
        return super()._special_status()

    def _special_art(self):
        if self._dying():
            grave = self.world.targets(self.player.id, "buried_at")
            town = self.world.entity(grave[0]) if grave else None
            if town is not None and town.kind == "town":
                return {"type": "scene", "terrain": town.data["terrain"], "settlement": town.data["kind"],
                        "watch": 3, "hall": None}
        return super()._special_art()

    def _gate(self, action: Action):
        if self._dying() and action.verb not in DEATH_VERBS:
            return self._turn([("You are dead. Choose how your story goes on.", "system")])
        return super()._gate(action)

    def _status_suffix(self) -> str:
        suffix = super()._status_suffix()
        age = self.player.data.get("age")
        if age is None or self._dying():
            return suffix
        near = ", lifespan near" if mortality.lifespan_near(self.world, self.player.id) else ""
        return f" ({int(age)}{near}){suffix}"

    def _before_scene(self) -> None:
        super()._before_scene()
        mortality.player_lived_to(self.world, self.player.id)  # the player's life clock starts with the first scene

    def _after_commit(self, ids: list, events: list) -> list:
        lines = super()._after_commit(ids, events)
        me = self.player.id
        if self._dying() or self.player.data.get("dead"):
            return lines
        for event_id, event in zip(ids, events):
            if event.kind == "deviation" and event.actors and event.actors[0] == me:
                deaths = mortality.deviation_death_events(self.world, me, event_id)
                if deaths:
                    return lines + self._commit(deaths) + self._death_lines()
        aged = mortality.age_events(self.world, me)
        if aged:
            commit(self.world, aged[:1])  # quiet: aging is not an event worth a line of prose
            if aged[0].data["white_hair"]:
                lines.append(("Your hair has gone white.", "dim"))
            if len(aged) > 1:
                lines += self._commit(aged[1:]) + self._death_lines()
        return lines

    def _do_new_world(self, _target):
        if not self._dying():
            return self._turn([("You are not dead.", "system")])
        self.exit_to = "title"
        return self._turn([("A new world awaits.", "system")])
```

- [ ] **Step 5: Write the narration** — `narrate/lineage_text.py`
```python
"""What the player is told about lineage (phase 4b)."""

from narrate.outcomes import outcome, summary


@outcome("player_aged", body_facts=False)
def _aged(world, event):
    return [], {}


@summary("player_aged")
def _aged_line(world, entry, names, place, other):
    return f"Grew older (now {int(entry.data['age'])})."
```

- [ ] **Step 6: Write the grammar** — `narrate/grammar/lineage.toml`
```toml
[symbols]
line_years = ["The years sit a little heavier.", "Another season is behind you.", "Time moves, as it always has.", "You feel the weight of years.", "The seasons turn.", "Something in you has grown older."]
line_quiet = ["No one else notices.", "The day goes on.", "You breathe slowly.", "The wind shifts.", "A bird calls somewhere.", "You carry on."]

[player_aged]
colour = "dim"
lines = ["#line_years# #line_quiet#", "#line_quiet# #line_years#"]
```

- [ ] **Step 7: Edit the existing files** — `.patches/4b_task1.py`
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
edit(GAME, "from engine.world_mixin import WorldMixin\n", "from engine.world_mixin import WorldMixin\nfrom engine.lineage import LineageMixin\n")
edit(GAME, "class Game(WorldMixin,", "class Game(LineageMixin, WorldMixin,")
edit(GAME, '''    def look(self) -> Turn:
        self.last_briefs = []
''', '''    def look(self) -> Turn:
        self.last_briefs = []
        if self.player.data.get("dying"):
            return self._turn(self._death_lines())  # the death screen, after a load (phase 4b)
''')
edit(GAME, '''QUIET_KINDS = frozenset({"exchange"})''', '''QUIET_KINDS = frozenset({"exchange", "player_aged"})''')
edit(GAME, '''            if not world.targets(player.id, "located_in"):
                raise SaveError''', '''            if not world.targets(player.id, "located_in") and not player.data.get("dying"):
                raise SaveError''')
edit(GAME, '''    def _do_look(self, _target) -> Turn:
        self.focus = None
''', '''    def _do_look(self, _target) -> Turn:
        if self.player.data.get("dying"):
            return self._turn(self._death_lines())
        self.focus = None
''')

APP = "app.py"
edit(APP, '''            turn = self.game.perform(action)
        except Exception as exc:  # the whole point: a bug becomes a report, not a dead game
            self.record_crash(exc, f"perform {action.verb}")
            return
        self._show(turn)''', '''            turn = self.game.perform(action)
        except Exception as exc:  # the whole point: a bug becomes a report, not a dead game
            self.record_crash(exc, f"perform {action.verb}")
            return
        self._show(turn)
        self._follow_exit()

    def _follow_exit(self) -> None:
        """After a death the player may leave for a new world or a newcomer (phase 4b spec 5.3)."""
        exit_to = getattr(self.game, "exit_to", None) if self.game is not None else None
        if exit_to == "title":
            self._close_game()
            self.state, self.selected = "title", 0
        elif exit_to == "newcomer":
            self._newcomer_save = self.save_path
            self._close_game()
            self.state, self.name, self.message = "name", "", ""''')
edit(APP, '''            elif choice == "New world":
                self.state, self.name, self.message = "name", "", ""''', '''            elif choice == "New world":
                self._newcomer_save = None
                self.state, self.name, self.message = "name", "", ""''')

edit("narrate/outcomes.py", "import narrate.world_text  # noqa: E402,F401\n",
     "import narrate.world_text  # noqa: E402,F401\nimport narrate.lineage_text  # noqa: E402,F401\n")

INV = "debug/invariants.py"
edit(INV, '''    problems += check_life(world, people)
''', '''    problems += check_life(world, people)
    problems += check_lineage(world)
''')
edit(INV, '''def check_sect(world) -> list[str]:''', '''def check_lineage(world) -> list[str]:
    """Phase 4b spec 8: exactly one living player, or a dead one choosing a successor."""
    out = []
    player_id = world.get_meta("player_id")
    player = world.entity(player_id) if player_id is not None else None
    if player is None:
        return out
    flagged = [p.id for p in world.entities("person") if p.data.get("is_player") and not p.data.get("dead")]
    if player.data.get("dead"):
        if not player.data.get("dying"):
            out.append("the player is dead but no successor is being chosen")
        if flagged:
            out.append(f"living people marked as the player while the player is dead: {flagged}")
    elif flagged != [player_id]:
        out.append(f"is_player marks {flagged}, but the player is #{player_id}")
    for ancestor in player.data.get("ancestors", []):
        entity = world.entity(ancestor)
        if entity is None or not entity.data.get("dead") or len(world.targets(ancestor, "buried_at")) != 1:
            out.append(f"ancestor #{ancestor} is not dead and buried")
    return out


def check_sect(world) -> list[str]:''')
edit(INV, '''        leaders = [p for p in living if F.membership(world, p, sect.id)[1].get("role") == "leader"]
        founder = sect.data["founder"]''', '''        founder = sect.data["founder"]
        if world.entity(founder).data.get("dead"):
            continue  # its founder has died and a successor is being chosen (phase 4b)
        leaders = [p for p in living if F.membership(world, p, sect.id)[1].get("role") == "leader"]''')
edit(INV, '''    known |= {p.name.lower() for p in world.entities("persona") if p.data.get("of") == player_id}''',
     '''    known |= {p.name.lower() for p in world.entities("persona") if p.data.get("of") == player_id}
    known |= {world.entity(k).name.lower() for k, _, _ in world.relations_from(player_id, "kin_of")}  # your family''')

FUZZ = "tests/test_fuzz.py"
text = Path(FUZZ).read_text(encoding="utf-8")
count = text.count('        assert app.state == "game", f"left the game at step {step}"')
if count != 6:
    raise SystemExit(f"{FUZZ}: expected 6 state assertions, found {count}")
text = text.replace('        assert app.state == "game", f"left the game at step {step}"', "        keep_playing(app, step)")
text = text.replace('''HOTKEYS = ["f2", "f3", "f4", "f12", "page up", "page down"]
''', '''HOTKEYS = ["f2", "f3", "f4", "f12", "page up", "page down"]


def keep_playing(app, step):
    """A death may end in a new world or a newcomer (phase 4b); carry the run on, then insist on play."""
    for _ in range(30):
        if app.state == "game":
            return
        if app.state == "title" and app.game is None:
            app.start_new("Again", world_seed=step + 1)
        else:
            app.handle_key("return", "\\r")
    assert app.state == "game", f"left the game at step {step}"
''')
Path(FUZZ).write_text(text, encoding="utf-8", newline="\n")
print("task 1 edits applied")
```

- [ ] **Step 8: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4b_task1.py && .venv/Scripts/python.exe -m pytest tests/test_mortality.py -q -p no:cacheprovider`
Expected: `task 1 edits applied`, then `7 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 9: Commit**

Run: `git add -A && git commit -m "feat: mortality - the player ages, can die of age or deviation, and faces the death screen"`

---
### Task 2: Killed in a fight, and the executioner

**Files:**
- Modify (via `.patches/4b_task2.py`):
  - `systems/mortality.py` (kill chances, trials, `record`);
  - `systems/duel.py` (a lost fight may be lethal);
  - `engine/roads.py` (hunters fight to kill);
  - `engine/law.py` (capital arrests);
  - `engine/lineage.py` (`_after_duel`);
  - `narrate/lineage_text.py`, `narrate/grammar/lineage.toml` (`tried`, `imprisoned`).
- Test: `tests/test_death_causes.py`

**Interfaces:**
- Consumes: Task 1 (`mortality.death_events`, `LineageMixin._death_lines`), 2b `duel._end_event`, `duel.yield_events`, `duel.Duel`, 3b `law._atone`, `law.WATCHES_PER_DAY`, `encounters.UNTALKABLE`, `encounters.encounter_events`, `encounters.encounter_state`.
- Produces:
  - `systems.mortality` (additions):
    - Constants: `CAPITAL = 150`, `KILL_CHANCE = {"grudge": 0.5, "hunter": 0.3, "ruthless": 0.1}`, `TRIAL_DEATH = 0.5`, `PRISON_SEASONS = 8`.
    - Fights: `ruthless(entity) -> bool`, `kill_chance(world, d, hateful) -> float`, `lethal(world, d, rng, hateful, reason) -> str | None` (`"killed"`, `"executed"` or `None`).
    - The law: `trial_events(world, player, place) -> list[Event]`.
  - `death_events` gains `record=True`. A duel death passes `record=False`, because the duel's own `killed` fact is the record.
  - Duel end data gains `player_killed` (a cause) and `killer`.
  - Events: `tried` (player, constable; data `verdict`, `facts`), `imprisoned` (player, constable; data `seasons`, `facts`).
  - Duel purposes: `{"hunter": True}` for sect and bounty hunters, `{"arrest": True, "capital": True}` for capital arrests.

- [ ] **Step 1: Write the failing test** — `tests/test_death_causes.py`
```python
import random
from types import SimpleNamespace

import pytest

import systems.duel as duel
import systems.encounters as encounters
import systems.mortality as mortality
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.creation import CreationChoice


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


def foe(game, path="test:foe", **data):
    return founding.make_person(game.world, path, game.place.id, **{"occupation": "hunter", "age": 30, **data})


def texts(turn):
    return [t for t, _ in turn.lines]


def lose(game, npc, reason="broken", purpose=None):
    game._start_duel(npc, "duel", purpose=purpose)
    d = game.combat
    event = (duel.yield_events(game.world, d)[0] if reason == "yielded"
             else duel._end_event(game.world, d, "lost", reason, random.Random(1), d.harm, 3))
    lines = game._commit([event])
    return lines + game._finish_duel(event.data)


def test_who_fights_to_kill(game):
    plain, cruel = foe(game, "test:plain", traits=["kind", "honest"]), foe(game, "test:cruel", traits=["cunning", "greedy"])
    duelist = SimpleNamespace(purpose={}, opponent=plain)
    assert mortality.kill_chance(game.world, duelist, False) == 0.0
    assert mortality.kill_chance(game.world, duelist, True) == 0.5
    assert mortality.kill_chance(game.world, SimpleNamespace(purpose={"hunter": True}, opponent=plain), False) == 0.3
    assert mortality.kill_chance(game.world, SimpleNamespace(purpose={}, opponent=cruel), False) == 0.1
    assert mortality.kill_chance(game.world, SimpleNamespace(purpose={"hunter": True}, opponent=cruel), True) == 0.5


def test_a_lost_fight_can_be_your_last(game, monkeypatch):
    monkeypatch.setitem(mortality.KILL_CHANCE, "grudge", 1.0)
    npc = foe(game)
    grudge = game.world.chronicle_about(game.player.id, limit=1)[0].id  # any moment the player took part in
    game.world.add_memory(npc, grudge, "hatred", 1.0, True)
    lines = lose(game, npc)
    dying = game.player.data["dying"]
    assert dying["cause"] == "killed" and dying["killer"] == npc
    assert len(game.world.facts(predicate="killed", subject=npc)) == 1
    assert any(t.startswith("Hero died at the hands of") for t, _ in lines)


def test_yielding_is_never_lethal_but_the_law_is(game, monkeypatch):
    for key in mortality.KILL_CHANCE:
        monkeypatch.setitem(mortality.KILL_CHANCE, key, 1.0)
    npc = foe(game, traits=["cunning", "greedy"])
    lose(game, npc, reason="yielded")
    assert not game.player.data.get("dying")
    constable = foe(game, "test:constable", occupation="constable")
    lose(game, constable, reason="yielded", purpose={"arrest": True, "capital": True})
    assert game.player.data["dying"]["cause"] == "executed"


def test_hunters_fight_to_kill(game):
    hunter = foe(game, "test:hunter")
    events = encounters.encounter_events(game.player.id, hunter, game.place.id, "bounty_hunter", 0)
    game._commit(events)
    game.encounter = encounters.encounter_state(events[-1])
    game.perform(Action("road", "fight"))
    assert game.combat is not None and game.combat.purpose == {"hunter": True}


def capital_arrest(game, bounty=200, path="test:officer"):
    constable = foe(game, path, occupation="constable")
    game.world.update_data(game.player.id, arrest={"constable": constable, "bounty": bounty, "facts": []})
    return constable


def test_a_capital_arrest_offers_only_trial_fight_or_flight(game):
    capital_arrest(game)
    verbs = [c.action.target for c in game.perform(Action("look")).choices]
    assert verbs == ["trial", "fight", "flee"]
    assert "cannot be paid" in texts(game.perform(Action("arrest", "pay")))[-1]


def test_a_trial_ends_in_death_or_two_years_in_prison(game, monkeypatch):
    capital_arrest(game)
    monkeypatch.setattr(mortality, "TRIAL_DEATH", 0.0)
    before = game.world.time
    game.perform(Action("arrest", "trial"))
    assert game.world.time >= before + mortality.PRISON_SEASONS * 360
    assert not game.player.data.get("arrest") and not game.player.data.get("dying")
    capital_arrest(game, path="test:officer2")
    monkeypatch.setattr(mortality, "TRIAL_DEATH", 1.0)
    game.perform(Action("arrest", "trial"))
    assert game.player.data["dying"]["cause"] == "executed"
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_death_causes.py -q -p no:cacheprovider`
Expected: failures such as `AttributeError: module 'systems.mortality' has no attribute 'kill_chance'`.

- [ ] **Step 3: Edit the existing files, adding fights and trials to mortality** — `.patches/4b_task2.py`
```python
"""Task 2 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


MORT = "systems/mortality.py"
edit(MORT, '''def death_events(world, player: int, cause: str, killer: int | None, age: float | None = None) -> list[Event]:
    place = lives.home(world, player)
    age = float(world.entity(player).data.get("age", 18)) if age is None else age
    return [Event("died", (killer or player, player), place, {"cause": cause, "player": True, "age": age})]''',
     '''def death_events(world, player: int, cause: str, killer: int | None, age: float | None = None,
                 record: bool = True) -> list[Event]:
    """`record=False` when a duel's own `killed` fact already tells the story."""
    place = lives.home(world, player)
    age = float(world.entity(player).data.get("age", 18)) if age is None else age
    return [Event("died", (killer or player, player), place,
                  {"cause": cause, "player": True, "age": age, "record": record})]''')
edit(MORT, '''    where = place_name(world, event.place)
    if killer == victim:
        record_fact(world, victim, "died", None''', '''    if not event.data.get("record", True):
        return
    where = place_name(world, event.place)
    if killer == victim:
        record_fact(world, victim, "died", None''')
Path(MORT).write_text(Path(MORT).read_text(encoding="utf-8") + '''

CAPITAL = 150
KILL_CHANCE = {"grudge": 0.5, "hunter": 0.3, "ruthless": 0.1}
TRIAL_DEATH = 0.5
PRISON_SEASONS = 8


def ruthless(entity) -> bool:
    traits = set(entity.data.get("traits", ()))
    return entity.data.get("occupation") == "bandit" or entity.data.get("roamer_kind") == "bandit" \\
        or {"cunning", "greedy"} <= traits


def kill_chance(world, d, hateful: bool) -> float:
    """How likely an opponent who has beaten the player is to finish them (spec 3.2): the highest row counts."""
    opponent = world.entity(d.opponent)
    if opponent is None or opponent.data.get("beast"):
        return 0.0
    if hateful:
        return KILL_CHANCE["grudge"]
    if (d.purpose or {}).get("hunter"):
        return KILL_CHANCE["hunter"]
    return KILL_CHANCE["ruthless"] if ruthless(opponent) else 0.0


def lethal(world, d, rng, hateful: bool, reason: str) -> str | None:
    """Whether losing this fight ends the player's life, and how. Yielding spares you, except from the law."""
    if (d.purpose or {}).get("capital"):
        return "executed"
    if reason == "yielded":
        return None
    chance = kill_chance(world, d, hateful)
    return "killed" if chance and rng.random() < chance else None


def trial_events(world, player: int, place: int) -> list[Event]:
    a = world.entity(player).data["arrest"]
    executed = rng_for(world.world_seed, f"trial:{player}:{world.time}").random() < TRIAL_DEATH
    events = [Event("tried", (player, a["constable"]), place,
                    {"verdict": "death" if executed else "prison", "facts": a["facts"]})]
    if executed:
        return events + death_events(world, player, "executed", a["constable"])
    return events + [Event("imprisoned", (player, a["constable"]), place,
                           {"seasons": PRISON_SEASONS, "facts": a["facts"]})]


@effect("tried")
def _tried(world, event) -> None:
    world.update_data(event.actors[0], arrest=None)


@effect("imprisoned")
def _imprisoned(world, event) -> None:
    from systems.law import _atone
    from systems.time import advance
    _atone(world, event.actors[0], event.data["facts"])
    advance(world, event.data["seasons"] * lives.SEASON)
''', encoding="utf-8", newline="\n")

edit("systems/duel.py", '''        chosen, amount, crippled = npc_verdict(rng, opponent, silver_of(world, d.player), hateful)
        data.update(''', '''        chosen, amount, crippled = npc_verdict(rng, opponent, silver_of(world, d.player), hateful)
        from systems.mortality import lethal  # losing can be the end (phase 4b spec 3.2)
        cause = lethal(world, d, rng, hateful, reason)
        if cause:
            chosen, amount, crippled = "kill", 0, None
            data.update(player_killed=cause, killer=d.opponent)
        data.update(''')

ROADS = "engine/roads.py"
text = Path(ROADS).read_text(encoding="utf-8")
old_calls = ('self._start_duel(person, "encounter"))', 'self._start_duel(person, "encounter", opening="opponent"))')
counts = [text.count(o) for o in old_calls]
if counts != [2, 1]:
    raise SystemExit(f"{ROADS}: expected 2 and 1 duel starts, found {counts}")
text = text.replace('self._start_duel(person, "encounter"))', 'self._start_duel(person, "encounter", purpose=self._road_purpose(e)))')
text = text.replace('self._start_duel(person, "encounter", opening="opponent"))',
                    'self._start_duel(person, "encounter", purpose=self._road_purpose(e), opening="opponent"))')
text = text.replace('''    def _do_road(self, how):''', '''    def _road_purpose(self, e: dict) -> dict | None:
        """Sect and bounty hunters came to kill (phase 4b spec 3.2)."""
        return {"hunter": True} if e["kind"] in encounters.UNTALKABLE else None

    def _do_road(self, how):''', 1)
Path(ROADS).write_text(text, encoding="utf-8", newline="\n")

LAW = "engine/law.py"
edit(LAW, '''            return [Choice(f"Pay the fine ({a['bounty']} silver)", Action("arrest", "pay")),''', '''            if a["bounty"] >= mortality.CAPITAL:  # a capital charge: no fine, no cell (phase 4b spec 3.4)
                return [Choice("Stand trial", Action("arrest", "trial")),
                        Choice("Fight your way free", Action("arrest", "fight")),
                        Choice("Try to flee", Action("arrest", "flee"))], []
            return [Choice(f"Pay the fine ({a['bounty']} silver)", Action("arrest", "pay")),''')
edit(LAW, '''        me, place = self.player.id, self.place.id
        if choice == "pay":''', '''        me, place = self.player.id, self.place.id
        capital = a["bounty"] >= mortality.CAPITAL
        if choice == "trial":
            if not capital:
                return self._turn([("Only a capital charge goes to trial.", "system")])
            lines = self._commit(mortality.trial_events(self.world, me, place))
            return self._turn(lines + (self._death_lines() if self._dying() else []))
        if capital and choice in ("pay", "jail"):
            return self._turn([("A capital charge cannot be paid or served away.", "system")])
        if choice == "pay":''')
edit(LAW, '''            return self._turn(lines + self._start_duel(a["constable"], "duel", purpose={"arrest": True}))''',
     '''            purpose = {"arrest": True, "capital": True} if capital else {"arrest": True}
            return self._turn(lines + self._start_duel(a["constable"], "duel", purpose=purpose))''')
edit(LAW, '''"""The law in the engine (phase 3b spec 8): arrest as a gated moment, like a challenge."""
''', '''"""The law in the engine (phase 3b spec 8): arrest as a gated moment, like a challenge."""

import systems.mortality as mortality
''')

LIN = "engine/lineage.py"
edit(LIN, '''    def _do_new_world(self, _target):''', '''    def _after_duel(self, data: dict) -> list:
        cause = data.get("player_killed")
        if not cause:
            return super()._after_duel(data)
        deaths = mortality.death_events(self.world, self.player.id, cause, data.get("killer"), record=False)
        return self._commit(deaths) + self._death_lines()  # nothing else follows a death

    def _do_new_world(self, _target):''')

edit("narrate/lineage_text.py", '''@outcome("player_aged", body_facts=False)''', '''@outcome("tried", body_facts=False)
def _tried(world, event):
    if event.data["verdict"] == "death":
        return ["The magistrate reads the sentence: death."], {}
    return ["The magistrate sentences you to two years in prison."], {}


@summary("tried")
def _tried_line(world, entry, names, place, other):
    return f"Stood trial in {place}."


@outcome("imprisoned", body_facts=False)
def _imprisoned(world, event):
    return ["Two years pass behind stone walls. You walk out a free, older person."], {}


@summary("imprisoned")
def _imprisoned_line(world, entry, names, place, other):
    return f"Spent {entry.data['seasons'] // 4} years in prison in {place}."


@outcome("player_aged", body_facts=False)''')
Path("narrate/grammar/lineage.toml").write_text(Path("narrate/grammar/lineage.toml").read_text(encoding="utf-8") + '''
[tried]
colour = "default"
lines = ["#line_court# #line_quiet#", "#line_quiet# #line_court#"]

[imprisoned]
colour = "dim"
lines = ["#line_years# #line_quiet#", "#line_quiet# #line_years#"]
''', encoding="utf-8", newline="\n")
edit("narrate/grammar/lineage.toml", '''line_quiet = [''', '''line_court = ["The court falls silent.", "A gong sounds once.", "The magistrate does not look up.", "Guards stand at your shoulders.", "Ink dries on the sentence.", "Someone in the crowd spits."]
line_quiet = [''')
print("task 2 edits applied")
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4b_task2.py && .venv/Scripts/python.exe -m pytest tests/test_death_causes.py tests/test_mortality.py -q -p no:cacheprovider`
Expected: `task 2 edits applied`, then `13 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 5: Commit**

Run: `git add -A && git commit -m "feat: lethal fights and capital trials - grudges and hunters can kill, the law can execute"`

---
### Task 3: Bonds: marriage, disciples, sworn siblings, a named heir, and who inherits

**Files:**
- Create: `systems/bonds.py`
- Modify (via `.patches/4b_task3.py`):
  - `systems/agendas.py` (children with the player);
  - `engine/lineage.py` (the bond verbs; clearing a named heir who is no longer valid);
  - `narrate/lineage_text.py`, `narrate/grammar/lineage.toml`, `narrate/world_text.py`.
- Test: `tests/test_bonds.py`

**Interfaces:**
- Consumes: 4a `agendas.spouse_of`, `children_of`, `_pair`, `birth_events`, `BIRTH_CHANCE`; `lives.current_season`, `lives.catch_up`; 3a `attitude`, `apparent_to`, `kin_of`, `kin.INVERSE`; 3c `founding.followers`, `founding.my_sect`, `sect.members`.
- Produces:
  - `systems.bonds`:
    - Constants: `MARRY_ATTITUDE = 0.5`, `DISCIPLE_ATTITUDE = 0.3`, `SWORN_ATTITUDE = 0.7`, `HEIR_AGE = 14`.
    - Attitude: `warmth(world, npc, player) -> float`, `accept_chance(score) -> float`.
    - Blocks (a reason, or `None` when allowed): `propose_block(world, player, npc)`, `disciple_block(world, player, npc)`, `sworn_block(world, player, npc)`.
    - Event builders, each `(world, player, npc, place)`: `propose_events`, `disciple_events`, `sworn_events`, `name_heir_events`.
    - Heirs: `candidates(world, player) -> list[tuple[int, str]]` (kind: `named`, `child`, `disciple`, `sibling` or `follower`), `relation_word(world, person, kind) -> str`.
  - Events: `proposal` (player, npc; data `accepted`, `season`), `took_disciple`, `sworn_siblings`, `named_heir`.
  - Facts: `married`, `apprenticed`, `sworn_siblings`.
  - Kin role `sworn_sibling`.
  - Engine verbs: `propose`, `take_disciple`, `swear`, `name_heir`.

- [ ] **Step 1: Write the failing test** — `tests/test_bonds.py`
```python
import pytest

import systems.agendas as agendas
import systems.bonds as bonds
import systems.encounters as encounters
import systems.lives as lives
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.creation import CreationChoice
from systems.kin import kin_of
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
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    for name in ("MARRY_CHANCE", "BIRTH_CHANCE", "MOVE_CHANCE", "REVENGE_CHANCE", "APPRENTICE_CHANCE"):
        monkeypatch.setattr(agendas, name, 0.0)


@pytest.fixture
def fond(monkeypatch):
    monkeypatch.setattr(bonds, "warmth", lambda world, npc, player: 1.0)


def local(game, path, **data):
    return founding.make_person(game.world, path, game.place.id, **{"occupation": "herbalist", **data})


def verbs(turn):
    return {c.action.verb for c in turn.all_choices}


def test_a_warm_friend_can_be_married(game, fond):
    npc = local(game, "test:love", age=25)
    assert "propose" in verbs(game.perform(Action("talk", npc)))
    game.perform(Action("propose", npc))
    assert agendas.spouse_of(game.world, game.player.id) == npc
    assert agendas.spouse_of(game.world, npc) == game.player.id
    assert game.world.facts(predicate="married", subject=game.player.id)


def test_a_refusal_stands_for_the_season(game, monkeypatch, fond):
    monkeypatch.setattr(bonds, "accept_chance", lambda score: 0.0)
    npc = local(game, "test:cold", age=25)
    game.perform(Action("talk", npc))
    game.perform(Action("propose", npc))
    assert agendas.spouse_of(game.world, game.player.id) is None
    assert bonds.propose_block(game.world, game.player.id, npc) == "They gave you their answer this season."


def test_the_player_can_have_children(game, monkeypatch, fond):
    monkeypatch.setattr(agendas, "BIRTH_CHANCE", 1.0)
    npc = local(game, "test:wife", age=28)
    game.perform(Action("talk", npc))
    game.perform(Action("propose", npc))
    lives.lived_to(game.world, npc)
    game.world.set_time(game.world.time + lives.SEASON)
    lives.catch_up(game.world, npc)
    [child] = agendas.children_of(game.world, game.player.id)
    assert agendas.children_of(game.world, npc) == [child]


def test_disciples_and_sworn_siblings(game, fond):
    youth, friend = local(game, "test:youth", age=16), local(game, "test:friend", age=30, gender="woman")
    game.perform(Action("talk", youth))
    game.perform(Action("take_disciple", youth))
    game.perform(Action("talk", friend))
    turn = game.perform(Action("swear", friend))
    assert (youth, "disciple") in kin_of(game.world, game.player.id)
    assert (friend, "sworn_sibling") in kin_of(game.world, game.player.id)
    assert (game.player.id, "sworn_sibling") in kin_of(game.world, friend)
    assert bonds.relation_word(game.world, friend, "sibling") == "your sworn sister"
    assert turn is not None


def test_heirs_come_in_order(game, fond):
    me = game.player.id
    elder, younger, small = local(game, "test:c1", age=30), local(game, "test:c2", age=20), local(game, "test:c3", age=9)
    for child in (elder, younger, small):
        agendas._pair(game.world, me, child, "child")
    pupil, sister = local(game, "test:pupil", age=17), local(game, "test:sister", age=40)
    agendas._pair(game.world, me, pupil, "disciple")
    agendas._pair(game.world, me, sister, "sworn_sibling")
    follower = local(game, "test:follower", age=35, sworn_to=me)
    assert bonds.candidates(game.world, me) == [(elder, "child"), (younger, "child"), (pupil, "disciple"),
                                                (sister, "sibling"), (follower, "follower")]
    game.perform(Action("talk", sister))
    game.perform(Action("name_heir", sister))
    assert bonds.candidates(game.world, me)[0] == (sister, "named")


def test_a_dead_named_heir_is_forgotten(game, fond):
    me = game.player.id
    heir, other = local(game, "test:heir", age=30), local(game, "test:other", age=20)
    agendas._pair(game.world, me, heir, "child")
    agendas._pair(game.world, me, other, "child")
    game.perform(Action("talk", heir))
    game.perform(Action("name_heir", heir))
    commit(game.world, [Event("died", (heir, heir), game.place.id, {"cause": "age", "world": True})])
    game.perform(Action("farewell"))
    game.perform(Action("meditate", 1))
    assert game.player.data.get("named_heir") is None
    assert bonds.candidates(game.world, me)[0] == (other, "child")
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_bonds.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.bonds'`.

- [ ] **Step 3: Write the bonds** — `systems/bonds.py`
```python
"""Bonds that make heirs (phase 4b spec 4): marriage, disciples, sworn siblings, and a named heir."""

import systems.agendas as agendas
import systems.lives as lives
import systems.sect as sect_mod
from systems.attitude import attitude
from systems.beliefs import apparent_to
from systems.facts import make_variant, place_name, record_fact
from systems.founding import followers, my_sect
from systems.kin import INVERSE, kin_of
from world.events import Event, effect, listen
from world.seed import rng_for

MARRY_ATTITUDE, DISCIPLE_ATTITUDE, SWORN_ATTITUDE = 0.5, 0.3, 0.7
HEIR_AGE = 14
INVERSE.setdefault("sworn_sibling", "sworn_sibling")


def warmth(world, npc: int, player: int) -> float:
    return attitude(world, npc, apparent_to(world, npc, player)).score


def accept_chance(score: float) -> float:
    return max(0.0, min(1.0, score))


def _age(entity) -> float:
    return float(entity.data.get("age", 30))


def _kin(world, person: int, role: str) -> list[int]:
    return [k for k, r in kin_of(world, person) if r == role]


def propose_block(world, player: int, npc: int) -> str | None:
    entity = world.entity(npc)
    if not 18 <= _age(entity) <= 50:
        return "They are not of an age to marry."
    if agendas.spouse_of(world, player) is not None:
        return "You are already married."
    if agendas.spouse_of(world, npc) is not None:
        return "They are already married."
    if npc in {k for k, _ in kin_of(world, player)}:
        return "They are family."
    refused = world.entity(player).data.get("spouse_refused", {})
    if refused.get(str(npc)) == lives.current_season(world):
        return "They gave you their answer this season."
    if warmth(world, npc, player) < MARRY_ATTITUDE:
        return "They do not feel that way about you."
    return None


def disciple_block(world, player: int, npc: int) -> str | None:
    entity = world.entity(npc)
    if not 12 <= _age(entity) <= 30:
        return "They are not of an age to be taught."
    if _kin(world, npc, "master"):
        return "They already have a master."
    if warmth(world, npc, player) < DISCIPLE_ATTITUDE:
        return "They would not follow your teaching."
    return None


def sworn_block(world, player: int, npc: int) -> str | None:
    if _age(world.entity(npc)) < 18:
        return "They are too young to swear an oath."
    if npc in _kin(world, player, "sworn_sibling"):
        return "You are already sworn."
    if warmth(world, npc, player) < SWORN_ATTITUDE:
        return "You are not close enough to swear an oath."
    return None


def propose_events(world, player: int, npc: int, place: int) -> list[Event]:
    n = lives.current_season(world)
    roll = rng_for(world.world_seed, f"propose:{player}:{npc}:{n}").random()
    accepted = roll < accept_chance(warmth(world, npc, player))
    return [Event("proposal", (player, npc), place, {"accepted": accepted, "season": n})]


def disciple_events(world, player: int, npc: int, place: int) -> list[Event]:
    return [Event("took_disciple", (player, npc), place, {})]


def sworn_events(world, player: int, npc: int, place: int) -> list[Event]:
    return [Event("sworn_siblings", (player, npc), place, {})]


def name_heir_events(world, player: int, npc: int, place: int) -> list[Event]:
    return [Event("named_heir", (player, npc), place, {})]


def candidates(world, player: int) -> list[tuple[int, str]]:
    """Who could carry on, in order (spec §4.2): named heir, children eldest first, disciples, sworn siblings, followers."""
    out: list[tuple[int, str]] = []
    seen: set[int] = set()

    def add(person, kind: str) -> None:
        entity = world.entity(person) if isinstance(person, int) else None
        if entity is None or person in seen or entity.kind != "person" or entity.data.get("dead") \
                or entity.data.get("is_player") or _age(entity) < HEIR_AGE:
            return
        seen.add(person)
        out.append((person, kind))

    add(world.entity(player).data.get("named_heir"), "named")
    for child in sorted(agendas.children_of(world, player), key=lambda p: (-_age(world.entity(p)), p)):
        add(child, "child")
    for pupil in _kin(world, player, "disciple"):
        add(pupil, "disciple")
    sect = my_sect(world, player)
    if sect is not None:
        members = sect_mod.members(world, sect)
        for person in sorted(members, key=lambda p: (-world.entity(p).data.get("loyalty", 0), -_age(world.entity(p)), p)):
            add(person, "disciple")
    for sibling in _kin(world, player, "sworn_sibling"):
        add(sibling, "sibling")
    for follower in followers(world, player):
        add(follower, "follower")
    return out


def relation_word(world, person: int, kind: str) -> str:
    woman = world.entity(person).data.get("gender") == "woman"
    return {"named": "your named heir", "child": "your daughter" if woman else "your son",
            "disciple": "your disciple", "sibling": "your sworn sister" if woman else "your sworn brother",
            "follower": "your sworn follower"}[kind]


@effect("proposal")
def _proposal(world, event) -> None:
    player, npc = event.actors
    if event.data["accepted"]:
        agendas._pair(world, player, npc, "spouse")
    else:
        refused = dict(world.entity(player).data.get("spouse_refused", {}))
        refused[str(npc)] = event.data["season"]
        world.update_data(player, spouse_refused=refused)


@effect("took_disciple")
def _took(world, event) -> None:
    agendas._pair(world, event.actors[0], event.actors[1], "disciple")


@effect("sworn_siblings")
def _sworn(world, event) -> None:
    agendas._pair(world, event.actors[0], event.actors[1], "sworn_sibling")


@effect("named_heir")
def _named(world, event) -> None:
    world.update_data(event.actors[0], named_heir=event.actors[1])


def _news(world, event, event_id: int, predicate: str) -> None:
    a, b = event.actors
    record_fact(world, a, predicate, b, place=event.place, source_event=event_id, weight=1.0,
                variant=make_variant(predicate, a, b, place=place_name(world, event.place)))


@listen("proposal")
def _proposal_news(world, event, event_id: int) -> None:
    if event.data["accepted"]:
        _news(world, event, event_id, "married")


@listen("took_disciple")
def _took_news(world, event, event_id: int) -> None:
    _news(world, event, event_id, "apprenticed")


@listen("sworn_siblings")
def _sworn_news(world, event, event_id: int) -> None:
    _news(world, event, event_id, "sworn_siblings")
```

- [ ] **Step 4: Edit the existing files** — `.patches/4b_task3.py`
```python
"""Task 3 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


edit("systems/agendas.py", '''    if spouse is None or spouse < person:  # the lower id of a couple rolls for both
        return []
    if not _ready(world, spouse, n):
        return []  # the spouse lives up to this season first (spec §2.2)''', '''    if spouse is None:
        return []
    with_player = bool(world.entity(spouse).data.get("is_player"))
    if spouse < person and not with_player:  # the lower id of a couple rolls for both; with the player, the NPC does
        return []
    if with_player:
        if world.entity(spouse).data.get("dead"):
            return []
    elif not _ready(world, spouse, n):
        return []  # the spouse lives up to this season first (spec §2.2)''')

LIN = "engine/lineage.py"
edit(LIN, '''import systems.mortality as mortality
''', '''import systems.bonds as bonds
import systems.mortality as mortality
''')
edit(LIN, '''    def _do_new_world(self, _target):''', '''    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        world, me = self.world, self.player.id
        if npc.data.get("beast") or npc.data.get("dead"):
            return extras
        if bonds.propose_block(world, me, npc.id) is None:
            extras.append(Choice("Propose marriage", Action("propose", npc.id)))
        if bonds.disciple_block(world, me, npc.id) is None and (npc.id, "disciple") not in bonds.kin_of(world, me):
            extras.append(Choice("Take them as your disciple", Action("take_disciple", npc.id)))
        if bonds.sworn_block(world, me, npc.id) is None:
            oath = "sisterhood" if npc.data.get("gender") == "woman" else "brotherhood"
            extras.append(Choice(f"Swear {oath}", Action("swear", npc.id)))
        heirs = [p for p, _ in bonds.candidates(world, me)]
        if npc.id in heirs and self.player.data.get("named_heir") != npc.id:
            extras.append(Choice("Name them your heir", Action("name_heir", npc.id)))
        return extras

    def _bond(self, npc, block, build):
        if self.focus != npc:
            return self._turn([("Speak with them first.", "system")])
        if block is not None and (why := block(self.world, self.player.id, npc)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(build(self.world, self.player.id, npc, self.place.id)))

    def _do_propose(self, npc):
        return self._bond(npc, bonds.propose_block, bonds.propose_events)

    def _do_take_disciple(self, npc):
        return self._bond(npc, bonds.disciple_block, bonds.disciple_events)

    def _do_swear(self, npc):
        return self._bond(npc, bonds.sworn_block, bonds.sworn_events)

    def _do_name_heir(self, npc):
        if npc not in [p for p, _ in bonds.candidates(self.world, self.player.id)]:
            return self._turn([("They cannot be your heir.", "system")])
        return self._bond(npc, None, bonds.name_heir_events)

    def _do_new_world(self, _target):''')
edit(LIN, '''        aged = mortality.age_events(self.world, me)''', '''        named = self.player.data.get("named_heir")
        if named is not None and named not in [p for p, _ in bonds.candidates(self.world, me)]:
            self.world.update_data(me, named_heir=None)  # a named heir who can no longer inherit is forgotten
        aged = mortality.age_events(self.world, me)''')

edit("narrate/world_text.py", '''    "apprenticed": "{actor} took {target} as a disciple.",''', '''    "apprenticed": "{actor} took {target} as a disciple.",
    "sworn_siblings": "{actor} swore an oath of kinship with {target}.",''')

edit("narrate/lineage_text.py", '''@outcome("player_aged", body_facts=False)''', '''@outcome("proposal", body_facts=False)
def _proposal(world, event):
    name = world.entity(event.actors[1]).name
    if event.data["accepted"]:
        return [f"{name} says yes. You are married."], {}
    return [f"{name} turns you down, gently but firmly."], {}


@summary("proposal")
def _proposal_line(world, entry, names, place, other):
    return f"Married {other}." if entry.data.get("accepted") else f"{other} turned down your proposal."


@outcome("took_disciple", body_facts=False)
def _took(world, event):
    return [f"{world.entity(event.actors[1]).name} kneels and becomes your disciple."], {}


@summary("took_disciple")
def _took_line(world, entry, names, place, other):
    return f"Took {other} as a disciple."


@outcome("sworn_siblings", body_facts=False)
def _sworn(world, event):
    return [f"You and {world.entity(event.actors[1]).name} swear to be kin."], {}


@summary("sworn_siblings")
def _sworn_line(world, entry, names, place, other):
    return f"Swore kinship with {other}."


@outcome("named_heir", body_facts=False)
def _named(world, event):
    return [f"You name {world.entity(event.actors[1]).name} your heir."], {}


@summary("named_heir")
def _named_line(world, entry, names, place, other):
    return f"Named {other} as heir."


@summary("born")
def _born_line(world, entry, names, place, other):
    return f"{names[2]} was born in {place}."


@outcome("player_aged", body_facts=False)''')

edit("narrate/grammar/lineage.toml", '''line_quiet = [''', '''line_bond = ["Something between you settles.", "A promise hangs in the air.", "You will remember this day.", "The world feels a little less wide.", "Tea is poured for two.", "Neither of you speaks for a moment."]
line_quiet = [''')
Path("narrate/grammar/lineage.toml").write_text(Path("narrate/grammar/lineage.toml").read_text(encoding="utf-8") + '''
[proposal]
colour = "npc"
lines = ["#line_bond# #line_quiet#", "#line_quiet# #line_bond#"]

[took_disciple]
colour = "npc"
lines = ["#line_bond# #line_quiet#", "#line_quiet# #line_bond#"]

[sworn_siblings]
colour = "npc"
lines = ["#line_bond# #line_quiet#", "#line_quiet# #line_bond#"]

[named_heir]
colour = "npc"
lines = ["#line_bond# #line_quiet#", "#line_quiet# #line_bond#"]
''', encoding="utf-8", newline="\n")
print("task 3 edits applied")
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4b_task3.py && .venv/Scripts/python.exe -m pytest tests/test_bonds.py -q -p no:cacheprovider`
Expected: `task 3 edits applied`, then `6 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 6: Commit**

Run: `git add -A && git commit -m "feat: bonds - marriage, children with the player, disciples, sworn siblings and a named heir"`

---
### Task 4: Succession: the heir takes up the mantle, or a newcomer begins

**Files:**
- Create: `systems/succession.py`
- Modify (via `.patches/4b_task4.py`):
  - `engine/lineage.py` (heirs on the death screen; `succeed`, `newcomer`);
  - `engine/game.py` (`Game.newcomer`);
  - `app.py` (starting a newcomer in the same save);
  - `narrate/lineage_text.py`, `narrate/grammar/lineage.toml`, `narrate/world_text.py`;
  - `debug/invariants.py` (a dead player's masks stay theirs; ruling 7).
- Test: `tests/test_succession.py`

**Interfaces:**
- Consumes:
  - Task 1: `mortality.epitaph`, `LineageMixin._death_choices`, `exit_to`, `App._follow_exit`, `App._newcomer_save`.
  - Task 3: `bonds.candidates`, `bonds.relation_word`.
  - 4a `lives.catch_up`, `lives.home`.
  - 2b `techniques.martial_arts`, `known_arts`, `teach`.
  - 3c `founding.my_sect`, `membership.set_membership`.
  - 1a `creation.build`, `apply_creation`.
- Produces:
  - `systems.succession`:
    - Constants: `SILVER = {"named": 1.0, "child": 1.0, "disciple": 0.75, "sibling": 0.5, "follower": 0.5}`, `ARTS = {"named": 0.7, "child": 0.7, "disciple": 0.7, "sibling": 0.5, "follower": 0.3}`.
    - `heir_kind(world, player, heir) -> str | None`, `succession_events(world, player, heir) -> list[Event]`, `newcomer_town(world, old) -> int`.
  - Event `succession` (old player, heir; data `kind`, `silver`, `arts`, `home`). Its effect moves wealth, items, land, the sect and arts, and switches the player. It writes the fact `heir_of` (subject = heir, object = old player; weight 2.0).
  - Player data: `ancestors` (oldest first).
  - `Game.newcomer(path, player_name, creation=None, narrator=None) -> Game`.
  - Engine verbs: `succeed` (target: the heir's id), `newcomer`.

- [ ] **Step 1: Write the failing test** — `tests/test_succession.py`
```python
import pytest

import systems.agendas as agendas
import systems.encounters as encounters
import systems.lives as lives
import systems.sect as sect_mod
from app import App
from config import Config
from debug.invariants import check_lineage, check_world
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.creation import CreationChoice
from systems.purse import silver_of
from systems.techniques import known_arts, martial_arts
from tests.test_sect import found_sect


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
    for name in ("MARRY_CHANCE", "BIRTH_CHANCE", "MOVE_CHANCE", "REVENGE_CHANCE", "APPRENTICE_CHANCE"):
        monkeypatch.setattr(agendas, name, 0.0)


def local(game, path, **data):
    return founding.make_person(game.world, path, game.place.id, **{"occupation": "herbalist", **data})


def die(game, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 1.0)
    turn = game.perform(Action("meditate", 90))
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    return turn


def texts(turn):
    return [t for t, _ in turn.lines]


def test_heirs_are_offered_on_the_death_screen(game, monkeypatch):
    son = local(game, "test:son", age=20, gender="man")
    agendas._pair(game.world, game.player.id, son, "child")
    turn = die(game, monkeypatch)
    assert [c.action.verb for c in turn.choices] == ["succeed", "newcomer", "new_world"]
    assert turn.choices[0].action.target == son and "your son" in turn.choices[0].label


def test_with_no_heir_only_a_fresh_start_is_offered(game, monkeypatch):
    turn = die(game, monkeypatch)
    assert [c.action.verb for c in turn.choices] == ["newcomer", "new_world"]


def test_a_child_inherits_everything(game, monkeypatch):
    world, old = game.world, game.player.id
    son = local(game, "test:son", age=20)
    agendas._pair(world, old, son, "child")
    world.update_data(old, silver=1000)
    token = world.add_entity("item", "Jade Token", {"kind": "curio"})
    world.relate(old, token, "owns")
    arts = {a.technique.id: a.completeness for a in martial_arts(world, old)}
    die(game, monkeypatch)
    turn = game.perform(Action("succeed", son))
    assert world.get_meta("player_id") == son and game.player.id == son
    assert world.entity(son).data["silver"] >= 1000 and world.entity(old).data["silver"] == 0
    assert world.targets(son, "owns") == [token] and world.targets(old, "owns") == []
    theirs = {a.technique.id: a.completeness for a in known_arts(world, son)}
    assert all(theirs[t] == pytest.approx(round(c * 0.7, 3)) for t, c in arts.items())
    assert world.entity(son).data["ancestors"] == [old]
    assert world.facts(predicate="heir_of", subject=son)[0].object == old
    assert not world.entity(old).data.get("is_player") and not world.entity(old).data.get("dying")
    assert check_lineage(world) == []
    assert any("You are" in t for t in texts(turn))


def test_a_follower_inherits_less(game, monkeypatch):
    world, old = game.world, game.player.id
    follower = local(game, "test:follower", age=30, sworn_to=old)
    world.update_data(old, silver=1000)
    arts = {a.technique.id: a.completeness for a in martial_arts(world, old)}
    die(game, monkeypatch)
    before = silver_of(world, follower)  # NPCs carry a seeded purse
    left = world.entity(old).data["silver"]  # what the dead player held at the end
    game.perform(Action("succeed", follower))
    assert silver_of(world, follower) == before + int(left * 0.5)
    theirs = {a.technique.id: a.completeness for a in known_arts(world, follower)}
    assert all(theirs[t] == pytest.approx(round(c * 0.3, 3)) for t, c in arts.items())
    assert not world.entity(follower).data.get("sworn_to")


def test_the_sect_and_its_land_pass_to_the_heir(game, monkeypatch):
    sect, town = found_sect(game)
    world, old = game.world, game.player.id
    disciple = sect_mod.members(world, sect)[0]
    world.update_data(disciple, age=25)
    die(game, monkeypatch)
    game.perform(Action("succeed", disciple))
    assert world.entity(sect).data["founder"] == disciple
    assert founding.my_sect(world, disciple) == sect
    assert world.targets(disciple, "owns_land") == [town] and world.targets(old, "owns_land") == []
    assert [p for p in check_world(world) if "sect" in p or "leader" in p] == []


def test_an_heir_away_on_duty_wakes_at_the_seat(game, monkeypatch):
    sect, town = found_sect(game)
    world = game.world
    disciple = sect_mod.members(world, sect)[0]
    world.update_data(disciple, age=25)
    game._commit(sect_mod.duty_events(world, game.player.id, disciple, town, True))
    die(game, monkeypatch)
    turn = game.perform(Action("succeed", disciple))
    assert world.targets(disciple, "located_in") == [town] and not world.entity(disciple).data["on_duty"]
    assert any(t.startswith("Here:") for t in texts(turn))


def test_a_newcomer_starts_in_the_same_world(tmp_path, monkeypatch):
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new("First", world_seed=11)
    old = app.game.player.id
    save = app.save_path
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 1.0)
    app.submit("meditate season")
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    app.submit(str(next(i for i, c in enumerate(app.choices, 1) if c.action.verb == "newcomer")))
    assert app.state == "name"
    for ch in "Second":
        app.handle_key(ch, ch)
    app.handle_key("return", "\r")
    app.handle_key("return", "\r")
    assert app.state == "game" and app.save_path == save
    world = app.game.world
    assert app.game.player.id != old and app.game.player.name == "Second"
    assert world.entity(old).data["dead"] and not world.entity(old).data.get("is_player")
    assert check_lineage(world) == [] and not world.entity(app.game.player.id).data.get("ancestors")
    app.shutdown()
    again = Game.load(save)
    assert again.start().choices and again.player.name == "Second"
    again.close()
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_succession.py -q -p no:cacheprovider`
Expected: failures, for example the choices are only `["new_world"]`.

- [ ] **Step 3: Write succession** — `systems/succession.py`
```python
"""Succession (phase 4b spec 5): the heir takes up your wealth, your arts and your name, and becomes you."""

import systems.bonds as bonds
import systems.lives as lives
from systems import factions as F
from systems.facts import make_variant, place_name, record_fact
from systems.founding import my_sect
from systems.membership import set_membership
from systems.purse import silver_of
from systems.techniques import known_arts, martial_arts, teach
from world.events import Event, effect, listen
from world.gen.materialize import ensure_town, region_of
from world.gen.region import region_spec
from world.seed import rng_for

SILVER = {"named": 1.0, "child": 1.0, "disciple": 0.75, "sibling": 0.5, "follower": 0.5}
ARTS = {"named": 0.7, "child": 0.7, "disciple": 0.7, "sibling": 0.5, "follower": 0.3}


def heir_kind(world, player: int, heir: int) -> str | None:
    return dict(bonds.candidates(world, player)).get(heir)


def _home_town(world, heir: int, sect: int | None) -> int:
    """Where the heir wakes: where they are, or the sect's seat if they are away on the roads (ruling 5)."""
    here = lives.home(world, heir)
    entity = world.entity(here) if here is not None else None
    if entity is not None and entity.kind == "town":
        return here
    if sect is not None:
        return world.entity(sect).data["seat"]
    region = entity if entity is not None and entity.kind == "region" else None
    x, y = (region.data["x"], region.data["y"]) if region is not None else (0, 0)
    return ensure_town(world, x, y, 0)


def succession_events(world, player: int, heir: int) -> list[Event]:
    lives.catch_up(world, heir)  # the heir has lived their own seasons, whatever the player missed
    kind = heir_kind(world, player, heir)
    if kind is None:
        return []
    silver = int(silver_of(world, player) * SILVER[kind])
    theirs = {a.technique.id: a.completeness for a in known_arts(world, heir)}
    arts = []
    for art in martial_arts(world, player):
        completeness = round(min(1.0, art.completeness * ARTS[kind]), 3)
        if theirs.get(art.technique.id, 0.0) < completeness:
            arts.append([art.technique.id, completeness])
    home = _home_town(world, heir, my_sect(world, player))
    return [Event("succession", (player, heir), home, {"kind": kind, "silver": silver, "arts": arts, "home": home})]


def newcomer_town(world, old: int) -> int:
    """A town within 3 regions of where the old player fell (spec §5.3)."""
    grave = world.targets(old, "buried_at")
    region = region_of(world, grave[0]) if grave and world.entity(grave[0]).kind == "town" else None
    x, y = (region.data["x"], region.data["y"]) if region is not None else (0, 0)
    rng = rng_for(world.world_seed, f"newcomer:{old}")
    x, y = x + rng.randint(-3, 3), y + rng.randint(-3, 3)
    return ensure_town(world, x, y, rng.randrange(region_spec(world.world_seed, x, y).town_count))


@effect("succession")
def _succession(world, event) -> None:
    old, heir = event.actors
    d = event.data
    world.update_data(heir, silver=silver_of(world, heir) + d["silver"])
    world.update_data(old, silver=0)
    for item in world.targets(old, "owns"):
        world.unrelate(old, "owns", item)
        world.relate(heir, item, "owns")
    for town in world.targets(old, "owns_land"):
        world.unrelate(old, "owns_land", town)
        world.relate(heir, town, "owns_land")
        if world.entity(town).data.get("owner") == old:
            world.update_data(town, owner=heir)
    sect = my_sect(world, old)
    if sect is not None:
        for fid, _, data in F.memberships(world, heir):
            kind = world.entity(fid).data["type"]
            if fid != sect and kind in F.MARTIAL and data.get("status", "member") == "member" and not data.get("secret"):
                set_membership(world, heir, fid, status="released")  # the heir renounces another martial faction
        world.relate(heir, sect, "member_of", 4,
                     {"role": "leader", "hall": None, "merit": 0, "status": "member", "secret": False})
        world.update_data(sect, founder=heir)
        world.update_data(old, sect=None)
        world.update_data(heir, sect=sect)
    for technique, completeness in d["arts"]:
        teach(world, heir, technique, completeness=completeness, known_completeness=completeness,
              source="inheritance", teacher=old)
    if lives.home(world, heir) != d["home"]:
        world.unrelate(heir, "located_in")
        world.relate(heir, d["home"], "located_in")
    ancestors = list(world.entity(old).data.get("ancestors", [])) + [old]
    world.update_data(old, is_player=False, dying=None, named_heir=None)
    world.update_data(heir, is_player=True, ancestors=ancestors, sworn_to=None, on_duty=False,
                      age=float(world.entity(heir).data.get("age", 18)))
    world.set_meta("player_id", heir)


@listen("succession")
def _heir_news(world, event, event_id: int) -> None:
    old, heir = event.actors
    record_fact(world, heir, "heir_of", old, place=event.place, source_event=event_id, weight=2.0,
                variant=make_variant("heir_of", heir, old, place=place_name(world, event.place)))
```

- [ ] **Step 4: Edit the existing files** — `.patches/4b_task4.py`
```python
"""Task 4 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


LIN = "engine/lineage.py"
edit(LIN, '''import systems.mortality as mortality
''', '''import systems.mortality as mortality
import systems.succession as succession
''')
edit(LIN, '''    def _death_choices(self) -> list:
        return [Choice("A new world", Action("new_world"))]''', '''    def _death_choices(self) -> list:
        choices = []
        for person, kind in bonds.candidates(self.world, self.player.id)[:8]:
            p = self.world.entity(person)
            where = self.world.entity(self.world.targets(person, "located_in")[0]).name \\
                if self.world.targets(person, "located_in") else "the roads"
            label = f"{p.name} - {bonds.relation_word(self.world, person, kind)}, {int(p.data.get('age', 30))}, " \\
                    f"{p.data.get('realm', 'mortal')}, in {where}"
            choices.append(Choice(label, Action("succeed", person)))
        return choices + [Choice("A newcomer in this world", Action("newcomer")), Choice("A new world", Action("new_world"))]''')
edit(LIN, '''    def _do_new_world(self, _target):''', '''    def _do_succeed(self, heir):
        if not self._dying():
            return self._turn([("You are not dead.", "system")])
        events = succession.succession_events(self.world, self.player.id, heir) if isinstance(heir, int) else []
        if not events:
            return self._turn([("They cannot carry on for you.", "system")])
        lines = self._commit(events)  # the player is now the heir
        self._last_look = None
        self._before_scene()
        return self._turn(lines + self._describe("arrive") + self._presence())

    def _do_newcomer(self, _target):
        if not self._dying():
            return self._turn([("You are not dead.", "system")])
        self.exit_to = "newcomer"
        return self._turn([("Someone new walks into this world.", "system")])

    def _do_new_world(self, _target):''')

GAME = "engine/game.py"
edit(GAME, '''    @classmethod
    def load(cls, path, narrator=None) -> "Game":''', '''    @classmethod
    def newcomer(cls, path, player_name: str, creation: CreationChoice | None = None, narrator=None) -> "Game":
        """A new character in a world whose last player has died (phase 4b spec 5.3)."""
        from systems.succession import newcomer_town
        world = World.open(path)
        old = world.get_meta("player_id")
        town = newcomer_town(world, old)
        made = build(world.world_seed + 7919 * int(old), creation or CreationChoice())
        with world.transaction():
            player = world.add_entity("person", player_name, {"is_player": True, "age": 18, "realm": "mortal"})
            world.relate(player, town, "located_in")
            world.set_meta("player_id", player)
            arts = apply_creation(world, player, made)
            world.update_data(old, is_player=False, dying=None)
        populate(world, town)
        settle_town(world, town)
        game = cls(world, narrator)
        game._pending = game._commit([Event("began", (player,), town, {"origin": made.origin.title, "arts": arts})])
        return game

    @classmethod
    def load(cls, path, narrator=None) -> "Game":''')

APP = "app.py"
edit(APP, '''    def start_new(self, name: str, world_seed: int | None = None, creation: CreationChoice | None = None) -> None:
        creation = creation or CreationChoice()''', '''    def start_new(self, name: str, world_seed: int | None = None, creation: CreationChoice | None = None) -> None:
        creation = creation or CreationChoice()
        newcomer_save = getattr(self, "_newcomer_save", None)
        if newcomer_save is not None:  # a newcomer walks into the dead player's world (phase 4b)
            self._newcomer_save = None
            self._close_game()
            self.game = Game.newcomer(newcomer_save, name, creation=creation)
            self.save_path = newcomer_save
            self._open_session(mode="newcomer", player=name, seed=self.game.world.world_seed,
                               creation=creation.to_dict())
            self.log = []
            self._show(self.game.start())
            self.state = "game"
            return''')

edit("narrate/world_text.py", '''    "sworn_siblings": "{actor} swore an oath of kinship with {target}.",''', '''    "sworn_siblings": "{actor} swore an oath of kinship with {target}.",
    "heir_of": "{actor} {be} the heir of {target}.",''')
edit("narrate/lineage_text.py", '''@outcome("player_aged", body_facts=False)''', '''@outcome("succession", body_facts=False)
def _succession(world, event):
    old, heir = (world.entity(a) for a in event.actors)
    return [f"You take up the mantle of {old.name}.", f"You are {heir.name} now."], {}


@summary("succession")
def _succession_line(world, entry, names, place, other):
    return f"Took up the mantle of {names[0]}."


@outcome("player_aged", body_facts=False)''')
Path("narrate/grammar/lineage.toml").write_text(Path("narrate/grammar/lineage.toml").read_text(encoding="utf-8") + '''
[succession]
colour = "gold"
lines = ["#line_bond# #line_years#", "#line_years# #line_bond#"]
''', encoding="utf-8", newline="\n")
edit("debug/invariants.py", """    for persona in world.entities("persona"):
        if persona.data.get("of") != player:""", """    for persona in world.entities("persona"):
        wearer = world.entity(persona.data["of"]) if isinstance(persona.data.get("of"), int) else None
        if persona.data.get("of") != player and (wearer is None or not wearer.data.get("dead")):  # a dead player's masks stay theirs""")
print("task 4 edits applied")
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4b_task4.py && .venv/Scripts/python.exe -m pytest tests/test_succession.py tests/test_mortality.py -q -p no:cacheprovider`
Expected: `task 4 edits applied`, then `14 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 6: Commit**

Run: `git add -A && git commit -m "feat: succession - heirs inherit wealth, arts, land and sect; a newcomer can start in the same world"`

---
### Task 5: Half-strength inheritance: name, feelings, standing, enemies, debts

**Files:**
- Create: `systems/lineage.py`
- Modify (via `.patches/4b_task5.py`): `systems/reputation.py`, `systems/attitude.py`, `systems/standing.py`, `systems/kin.py` (`avengers_for`), `systems/law.py` (`bounty`)
- Test: `tests/test_inheritance.py`

**Interfaces:**
- Consumes: Task 4 (the `heir_of` fact, player data `ancestors`), 3a `beliefs.home_of`, `world.believers`, 3b `standing._towns`, `kin.avengers_for`.
- Produces:
  - `systems.lineage`:
    - Constants: `FACTOR = 0.5`, `GRUDGE_SHARE = 0.5`.
    - Who knows: `predecessor(world, heir) -> int | None`, `believes(world, knower, heir, ancestor) -> bool` (the knower, their home town, or one of their faction's towns holds `heir_of`).
    - Uses: `inherited(world, knower, heir) -> list[tuple[int, float]]`, `inherited_avengers(world, heir) -> list[int]`.
  - `reputation`, `attitude`, `standing`, `avengers_for` and `bounty` each add the predecessor's share (spec §6). The old `reputation` body becomes `_own_reputation`.

- [ ] **Step 1: Write the failing test** — `tests/test_inheritance.py`
```python
import pytest

import systems.agendas as agendas
import systems.encounters as encounters
import systems.lineage as lineage
import systems.lives as lives
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import founding, halls, law
from systems.attitude import attitude
from systems.beliefs import believe
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from systems.kin import avengers_for
from systems.reputation import reputation
from systems.standing import _towns, standing
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
    for name in ("MARRY_CHANCE", "BIRTH_CHANCE", "MOVE_CHANCE", "REVENGE_CHANCE", "APPRENTICE_CHANCE"):
        monkeypatch.setattr(agendas, name, 0.0)


def local(game, path, **data):
    return founding.make_person(game.world, path, game.place.id, **{"occupation": "herbalist", "age": 30, **data})


def deed(game, predicate, target, weight=3.0):
    me, town = game.player.id, game.place.id
    return record_fact(game.world, me, predicate, target, place=town, weight=weight,
                       variant=make_variant(predicate, me, target, place=game.world.entity(town).name))


def succeed(game, monkeypatch, heir):
    """Die of age and carry on as `heir`, a child of the player."""
    agendas._pair(game.world, game.player.id, heir, "child")
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 1.0)
    game.perform(Action("meditate", 90))
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    old = game.player.id
    game.perform(Action("succeed", heir))
    return old


def test_the_town_knows_the_heir_by_the_old_name(game, monkeypatch):
    town = game.place.id
    for i in range(4):
        deed(game, "defeated", local(game, f"test:beaten:{i}"))
    son = local(game, "test:son", age=20)
    old = succeed(game, monkeypatch, son)
    theirs, mine = reputation(game.world, town, old), reputation(game.world, town, son)
    assert mine.renown >= 0.5 * theirs.renown > 0
    assert lineage.inherited(game.world, town, son) == [(old, 0.5)]


def test_a_name_unheard_of_carries_nothing(game, monkeypatch):
    son = local(game, "test:son", age=20)
    old = succeed(game, monkeypatch, son)
    far = F.ensure_roster(game.world)[0]
    assert lineage.inherited(game.world, game.world.entity(far).data["seat"] or 999999, son) == []
    assert lineage.predecessor(game.world, son) == old


def test_old_gratitude_warms_to_the_heir(game, monkeypatch):
    friend = local(game, "test:friend")
    moment = game.world.chronicle_about(game.player.id, limit=1)[0].id
    game.world.add_memory(friend, moment, "grateful", 1.0, True)
    son = local(game, "test:son", age=20)
    cold = attitude(game.world, friend, son).score
    succeed(game, monkeypatch, son)
    assert attitude(game.world, friend, son).score > cold


def test_a_faction_judges_the_heir_by_the_founder(game, monkeypatch):
    world, me = game.world, game.player.id
    faction = next(f for f in F.ensure_roster(world) if world.entity(f).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, faction)
    spared = founding.make_person(world, "test:spared", seat, occupation="hunter", age=30)
    record_fact(world, me, "spared", spared, place=seat, weight=3.0,  # a mercy the righteous heard of
                variant=make_variant("spared", me, spared, place=world.entity(seat).name))
    son = local(game, "test:son", age=20)
    old = succeed(game, monkeypatch, son)
    fact = game.world.facts(predicate="heir_of", subject=son)[0]
    for town in _towns(game.world, faction):
        believe(game.world, town, fact.id, fact.variant, None, 1.0, 0, "test")
    theirs = standing(game.world, faction, old).score
    assert theirs > 0 and standing(game.world, faction, son).score == pytest.approx(0.5 * theirs, abs=0.002)


def test_avengers_turn_on_the_heir(game, monkeypatch):
    monkeypatch.setattr(lineage, "GRUDGE_SHARE", 1.0)
    victim = local(game, "test:victim", kin_ready=True)
    brother = local(game, "test:brother", kin_ready=True)
    game.world.relate(victim, brother, "kin_of", data={"role": "sibling"})
    game.world.relate(brother, victim, "kin_of", data={"role": "sibling"})
    commit(game.world, [Event("died", (game.player.id, victim), game.place.id, {"cause": "killed"})])
    son = local(game, "test:son", age=20)
    old = succeed(game, monkeypatch, son)
    assert brother in avengers_for(game.world, old)
    assert brother in avengers_for(game.world, son)


def test_the_heir_answers_for_half_the_debts(game, monkeypatch):
    town = game.place.id
    for i in range(3):
        deed(game, "killed", local(game, f"test:slain:{i}"))
    son = local(game, "test:son", age=20)
    old = succeed(game, monkeypatch, son)
    theirs = law.bounty(game.world, town, old)
    assert theirs > 0 and law.bounty(game.world, town, son) == round(0.5 * theirs)
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_inheritance.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'systems.lineage'`.

- [ ] **Step 3: Write the lineage rules** — `systems/lineage.py`
```python
"""Half-strength inheritance (phase 4b spec 6): an heir is judged, in part, by the one they succeeded.

Only among those who believe the heir is the heir: the knower, their home town,
or (for a faction) one of its towns must hold the `heir_of` fact. Only the
direct predecessor is consulted; earlier ancestors reach the heir through them,
halving again each generation.
"""

from world.seed import rng_for

FACTOR = 0.5         # how much of the predecessor's name, feelings, standing and debts pass on
GRUDGE_SHARE = 0.5   # the share of the predecessor's avengers who carry the grudge to the heir


def predecessor(world, heir) -> int | None:
    entity = world.entity(heir) if isinstance(heir, int) else None
    ancestors = entity.data.get("ancestors") if entity is not None and entity.kind == "person" else None
    return ancestors[-1] if ancestors else None


def _heir_fact(world, heir: int, ancestor: int) -> int | None:
    """The `heir_of` fact's id (world._cached keeps lists, so the one value travels in a list)."""
    return world._cached(("heir_fact", heir, ancestor), lambda: [next(
        (f.id for f in world.facts(predicate="heir_of", subject=heir) if f.object == ancestor), None)])[0]


def _knowers(world, fact_id: int) -> set:
    return set(world._cached(("heir_knowers", fact_id), lambda: [b.knower for b in world.believers(fact_id)]))


def believes(world, knower, heir: int, ancestor: int) -> bool:
    fact = _heir_fact(world, heir, ancestor)
    if fact is None or not isinstance(knower, int):
        return False
    knowers = _knowers(world, fact)
    if knower in knowers:
        return True
    entity = world.entity(knower)
    if entity is None:
        return False
    if entity.kind == "person":
        from systems.beliefs import home_of
        return home_of(world, knower) in knowers
    if entity.kind == "faction":
        from systems.standing import _towns
        return bool(knowers & set(_towns(world, knower)))
    return False


def inherited(world, knower, heir) -> list[tuple[int, float]]:
    """[(predecessor, share)] when this knower takes the heir for the predecessor's heir; else []."""
    old = predecessor(world, heir)
    if old is None:
        return []
    return [(old, FACTOR)] if believes(world, knower, heir, old) else []


def inherited_avengers(world, heir: int) -> list[int]:
    old = predecessor(world, heir)
    if old is None:
        return []
    from systems.kin import avengers_for
    out = []
    for avenger in avengers_for(world, old):
        if avenger == heir or not believes(world, avenger, heir, old):
            continue
        if rng_for(world.world_seed, f"heir-grudge:{avenger}:{heir}").random() < GRUDGE_SHARE:
            out.append(avenger)
    return out
```

- [ ] **Step 4: Edit the existing files** — `.patches/4b_task5.py`
```python
"""Task 5 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


REP = "systems/reputation.py"
edit(REP, '''def reputation(world, town_id: int, subject_id: int) -> Reputation:''',
     '''def _own_reputation(world, town_id: int, subject_id: int) -> Reputation:''')
Path(REP).write_text(Path(REP).read_text(encoding="utf-8") + '''

def reputation(world, town_id: int, subject_id: int) -> Reputation:
    """What a town makes of someone, including half of the name they inherited (phase 4b spec 6)."""
    own = _own_reputation(world, town_id, subject_id)
    from systems.lineage import inherited
    extra, shadow = 0.0, None
    for ancestor, share in inherited(world, town_id, subject_id):
        old = reputation(world, town_id, ancestor)
        extra += share * old.renown
        name = world.entity(ancestor).name
        shadow = shadow or (f"heir of the {old.epithet}" if old.epithet else f"heir of {name}" if old.renown else None)
    if not extra:
        return own
    renown = round(own.renown + extra, 3)
    return Reputation(renown, renown_word(renown), own.path if own.renown else "hard to read", own.epithet or shadow)
''', encoding="utf-8", newline="\n")

edit("systems/attitude.py", '''    terms += list(best.values())
    if "kind" in traits:''', '''    terms += list(best.values())
    from systems.lineage import inherited  # an heir is remembered, in part, as the one before (phase 4b)
    for ancestor, share in inherited(world, npc_id, true_id):
        for memory in world.memories(npc_id, about=ancestor):
            value = FEELING_VALUE.get(memory.feeling, 0.0) * effective_intensity(memory, now) * share
            if value:
                terms.append((value, "they remember the one who came before you"))
    if "kind" in traits:''')

edit("systems/standing.py", '''    score = round(sum(v for v, _ in terms), 3)''', '''    from systems.lineage import inherited  # a faction judges an heir, in part, by the one before (phase 4b)
    for ancestor, share in inherited(world, faction_id, subject):
        old = standing(world, faction_id, ancestor).score
        if old:
            terms.append((share * old, "the one who came before you"))
    score = round(sum(v for v, _ in terms), 3)''')

edit("systems/kin.py", '''    return found
''', '''    from systems.lineage import inherited_avengers  # grudges outlive the one they were held against (phase 4b)
    return found + [a for a in inherited_avengers(world, player_id) if a not in found]
''')

edit("systems/law.py", '''    amount = round(FINE_PER * sum(w for _, w in crimes(world, town_id, subject)))''', '''    amount = round(FINE_PER * sum(w for _, w in crimes(world, town_id, subject)))
    from systems.lineage import inherited  # an heir answers for half the debts they inherited (phase 4b)
    amount += sum(round(share * bounty(world, town_id, a)) for a, share in inherited(world, town_id, subject))''')
print("task 5 edits applied")
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4b_task5.py && .venv/Scripts/python.exe -m pytest tests/test_inheritance.py -q -p no:cacheprovider`
Expected: `task 5 edits applied`, then `6 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 6: Commit**

Run: `git add -A && git commit -m "feat: half-strength inheritance - an heir carries half the name, feelings, standing, enemies and debts"`

---
### Task 6: The lineage page (F8), relations in briefs, lineage rules, a short dangerous life, docs

**Files:**
- Create: `engine/lineage_page.py`, `tests/test_lineage_page.py`
- Modify (via `.patches/4b_task6.py`):
  - `systems/succession.py` (keep how the ancestor died);
  - `engine/lineage.py` (the `lineage` verb);
  - `engine/commands.py`, `app.py` (F8);
  - `engine/game.py` (help text);
  - `narrate/brief.py`, `narrate/lineage_text.py` (relations in briefs);
  - `debug/invariants.py` (rules 4 and 5);
  - `tests/test_fuzz.py` (a short, dangerous life);
  - `docs/debugging.md`.
- Test: `tests/test_lineage_page.py`

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces:
  - `engine.lineage_page.lineage_lines(world, player) -> list[Line]`.
  - The verb `lineage` (typed, or F8).
  - `narrate.lineage_text.relation_fact(world, player, other) -> str | None`.
  - Ancestor data `death` (the `dying` record, kept at succession).
  - `check_lineage` gains rules 4 (the named heir is alive) and 5 (ancestors own nothing).
  - The fuzz test `test_a_short_dangerous_life`.

- [ ] **Step 1: Write the failing test** — `tests/test_lineage_page.py`
```python
import time

import pytest

import systems.agendas as agendas
import systems.encounters as encounters
import systems.lives as lives
from app import App
from config import Config
from debug.invariants import check_lineage
from engine.actions import Action
from engine.game import Game
from engine.lineage_page import lineage_lines
from systems import founding
from systems.creation import CreationChoice


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
    for name in ("MARRY_CHANCE", "BIRTH_CHANCE", "MOVE_CHANCE", "REVENGE_CHANCE", "APPRENTICE_CHANCE"):
        monkeypatch.setattr(agendas, name, 0.0)


def local(game, path, **data):
    return founding.make_person(game.world, path, game.place.id, **{"occupation": "herbalist", "age": 30, **data})


def texts(lines):
    return [t for t, _ in lines]


def succeed(game, monkeypatch, heir):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 1.0)
    game.perform(Action("meditate", 90))
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    game.perform(Action("succeed", heir))


def test_the_page_lists_family_and_who_would_inherit(game):
    me = game.player.id
    son, wife = local(game, "test:son", age=20, gender="man"), local(game, "test:wife", gender="woman")
    agendas._pair(game.world, me, son, "child")
    agendas._pair(game.world, me, wife, "spouse")
    lines = texts(game.perform(Action("lineage")).lines)
    name = game.world.entity(son).name
    assert lines[0] == "Your lineage"
    assert any(t.startswith("  Spouse: " + game.world.entity(wife).name) for t in lines)
    assert any(t.startswith(f"  Child: {name}, 20") for t in lines)
    assert "If you died today:" in lines and any(t.startswith(f"  1. {name}") for t in lines)


def test_ancestors_are_remembered_with_how_they_died(game, monkeypatch):
    son = local(game, "test:son", age=20)
    agendas._pair(game.world, game.player.id, son, "child")
    succeed(game, monkeypatch, son)
    lines = texts(lineage_lines(game.world, game.player.id))
    assert "Ancestors:" in lines and any("Hero, died of old age in" in t for t in lines)
    assert check_lineage(game.world) == []


def test_f8_opens_the_page(tmp_path):
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new("Elder", world_seed=11)
    app.handle_key("f8", "")
    assert any(text == "Your lineage" for text, _ in app.log)
    app.shutdown()


def test_briefs_name_the_relation(game):
    son = local(game, "test:son", age=20, gender="man")
    agendas._pair(game.world, game.player.id, son, "child")
    game.perform(Action("talk", son))
    assert f"{game.world.entity(son).name} is your son." in game.last_briefs[-1].facts


def test_an_ancestor_who_still_owns_things_is_caught(game, monkeypatch):
    son = local(game, "test:son", age=20)
    agendas._pair(game.world, game.player.id, son, "child")
    old = game.player.id
    succeed(game, monkeypatch, son)
    game.world.update_data(old, silver=5)
    assert any("still holds" in p for p in check_lineage(game.world))


def test_succession_and_the_page_are_quick(game, monkeypatch):
    me = game.player.id
    for i in range(30):
        agendas._pair(game.world, me, local(game, f"test:kin:{i}", age=20 + i), "child")
    start = time.perf_counter()
    lineage_lines(game.world, me)
    page = time.perf_counter() - start
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 1.0)
    game.perform(Action("meditate", 90))
    start = time.perf_counter()
    game.perform(Action("succeed", game.world.relations_from(me, "kin_of")[0][0]))
    step = time.perf_counter() - start
    assert page < 0.05 and step < 0.1, f"page {page * 1000:.0f} ms, succession {step * 1000:.0f} ms"
```

- [ ] **Step 2: Run the test to see it fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_lineage_page.py -q -p no:cacheprovider`
Expected: the collection error `ModuleNotFoundError: No module named 'engine.lineage_page'`.

- [ ] **Step 3: Write the page** — `engine/lineage_page.py`
```python
"""The lineage page (F8, phase 4b spec 7): who came before you, who is yours, and who would carry on."""

import systems.agendas as agendas
import systems.bonds as bonds
import systems.mortality as mortality
from narrate.base import Line
from systems.facts import place_name
from systems.founding import followers
from systems.kin import kin_of


def _someone(world, person: int) -> str:
    p = world.entity(person)
    here = world.targets(person, "located_in")
    where = world.entity(here[0]).name if here else "the roads"
    return f"{p.name}, {int(p.data.get('age', 30))}, {p.data.get('realm', 'mortal')}, in {where}"


def _ancestor(world, person: int) -> str:
    p = world.entity(person)
    death = p.data.get("death") or {}
    killer = world.entity(death["killer"]).name if death.get("killer") else "someone"
    how = mortality.CAUSES.get(death.get("cause"), "").format(killer=killer)
    where = place_name(world, death.get("place")) or "the road"
    return f"  {p.name}, died {how} in {where}, aged {int(death.get('age') or p.data.get('age', 0))}"


def lineage_lines(world, player: int) -> list[Line]:
    lines: list[Line] = [("Your lineage", "heading")]
    ancestors = world.entity(player).data.get("ancestors", [])
    if ancestors:
        lines.append(("Ancestors:", "heading"))
        lines += [(_ancestor(world, a), "dim") for a in ancestors]
    lines.append(("Family and bonds:", "heading"))
    spouse = agendas.spouse_of(world, player)
    rows = []
    if spouse is not None:
        rows.append(f"  Spouse: {_someone(world, spouse)}")
    for role, word in (("child", "Child"), ("disciple", "Disciple"), ("sworn_sibling", "Sworn sibling")):
        rows += [f"  {word}: {_someone(world, k)}" for k, r in kin_of(world, player) if r == role]
    rows += [f"  Sworn follower: {_someone(world, f)}" for f in followers(world, player)]
    lines += [(row, "dim") for row in rows] or [("  none yet", "dim")]
    named = world.entity(player).data.get("named_heir")
    if named is not None:
        lines.append((f"Named heir: {world.entity(named).name}", "dim"))
    lines.append(("If you died today:", "heading"))
    heirs = bonds.candidates(world, player)[:3]
    lines += [(f"  {i}. {world.entity(p).name} ({bonds.relation_word(world, p, kind)})", "dim")
              for i, (p, kind) in enumerate(heirs, 1)] or [("  no one would carry on your name", "dim")]
    return lines
```

- [ ] **Step 4: Edit the existing files** — `.patches/4b_task6.py`
```python
"""Task 6 edits to existing files. Each edit must match exactly once."""
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}")
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


edit("systems/succession.py", '''    world.update_data(old, is_player=False, dying=None, named_heir=None)''',
     '''    world.update_data(old, is_player=False, death=world.entity(old).data.get("dying"), dying=None, named_heir=None)''')

LIN = "engine/lineage.py"
edit(LIN, '''    def _do_new_world(self, _target):''', '''    def _do_lineage(self, _target):
        from engine.lineage_page import lineage_lines
        return self._turn(lineage_lines(self.world, self.player.id))

    def _do_new_world(self, _target):''')
edit("engine/commands.py", '''"ledger": Action("ledger"),''', '''"ledger": Action("ledger"), "lineage": Action("lineage"),''')
edit("app.py", '''        elif key == "f7":
            self.submit("ledger")''', '''        elif key == "f7":
            self.submit("ledger")
        elif key == "f8":
            self.submit("lineage")''')
edit("engine/game.py", '''standing (F6) | ledger (F7)"''', '''standing (F6) | ledger (F7) | lineage (F8)"''')

edit("narrate/lineage_text.py", '''from narrate.outcomes import outcome, summary
''', '''from narrate.outcomes import outcome, summary

WORDS = {"child": ("your son", "your daughter"), "spouse": ("your husband", "your wife"),
         "disciple": ("your disciple", "your disciple"), "sworn_sibling": ("your sworn brother", "your sworn sister"),
         "parent": ("your father", "your mother"), "master": ("your master", "your master")}


def relation_fact(world, player: int, other) -> str | None:
    """One brief line naming how someone stands to the player (phase 4b spec 7)."""
    if other is None or other.id == player:
        return None
    woman = other.data.get("gender") == "woman"
    for kin, _, data in world.relations_from(player, "kin_of"):
        if kin == other.id and data.get("role") in WORDS:
            return f"{other.name} is {WORDS[data['role']][1 if woman else 0]}."
    if other.data.get("sworn_to") == player:
        return f"{other.name} is your sworn follower."
    return None
''')
BRIEF = "narrate/brief.py"
edit(BRIEF, '''        from narrate.world_text import life_facts  # age and family (phase 4a)
        facts = facts + [f for f in life_facts(world, other) if f not in facts]''', '''        from narrate.world_text import life_facts  # age and family (phase 4a)
        from narrate.lineage_text import relation_fact  # and how they stand to you (phase 4b)
        related = relation_fact(world, player.id, other)
        facts = ([related] if related else []) + facts + [f for f in life_facts(world, other) if f not in facts]''')
edit(BRIEF, '''    news = town_news(world, place_id, player_id)''', '''    news = town_news(world, place_id, player_id)
    ancestors = player.data.get("ancestors") or []
    if ancestors:
        facts.append(f"You are the heir of {world.entity(ancestors[-1]).name}.")''')

INV = "debug/invariants.py"
edit(INV, '''    for ancestor in player.data.get("ancestors", []):
        entity = world.entity(ancestor)
        if entity is None or not entity.data.get("dead") or len(world.targets(ancestor, "buried_at")) != 1:
            out.append(f"ancestor #{ancestor} is not dead and buried")''', '''    for ancestor in player.data.get("ancestors", []):
        entity = world.entity(ancestor)
        if entity is None or not entity.data.get("dead") or len(world.targets(ancestor, "buried_at")) != 1:
            out.append(f"ancestor #{ancestor} is not dead and buried")
        elif entity.data.get("silver", 0) or world.targets(ancestor, "owns") or world.targets(ancestor, "owns_land"):
            out.append(f"ancestor #{ancestor} still holds silver, items or land")
    named = player.data.get("named_heir")
    if named is not None and not player.data.get("dying") and (world.entity(named) is None or world.entity(named).data.get("dead")):
        out.append(f"the named heir #{named} is dead")''')

FUZZ = "tests/test_fuzz.py"
Path(FUZZ).write_text(Path(FUZZ).read_text(encoding="utf-8") + '''

@pytest.mark.parametrize("seed", [6, 17])
def test_a_short_dangerous_life(tmp_path, seed, monkeypatch):
    """Everyone fights to kill and age comes quickly: death, heirs and newcomers again and again, every rule held."""
    import systems.lives as lives
    import systems.mortality as mortality
    for key in mortality.KILL_CHANCE:
        monkeypatch.setitem(mortality.KILL_CHANCE, key, 1.0)
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.08)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 2.0)
    rng = random.Random(seed)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new(f"Mayfly{seed}", world_seed=seed)
    for step in range(300):
        game = app.game
        if game.combat is not None or game.encounter is not None or game.challenger is not None:
            app.submit(rng.choice(FIGHTING + ["1", "2"]))
        elif app.choices and rng.random() < 0.5:
            app.submit(str(rng.randint(1, len(app.choices))))
        else:
            app.submit(rng.choice(["meditate season", "challenge", "go north", "go east", "go south", "go west",
                                   "look", "lineage", "journal", "1", "2"]))
        keep_playing(app, step)
    assert app.crash_count == 0, list((tmp_path / "logs").glob("crash-*"))
    assert app.violations == [], app.violations[:5]
    app.shutdown()
''', encoding="utf-8", newline="\n")

edit("docs/debugging.md", '''- **The living world (phase 4a):**''', '''- **Lineage (phase 4b):** exactly one living person is the player, or the player is dead and choosing a successor (the death screen); every ancestor is dead, buried and owns nothing; a named heir is alive. The fuzz run `test_a_short_dangerous_life` dies and succeeds many times.
- **The living world (phase 4a):**''')
print("task 6 edits applied")
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe .patches/4b_task6.py && .venv/Scripts/python.exe -m pytest tests/test_lineage_page.py -q -p no:cacheprovider`
Expected: `task 6 edits applied`, then `6 passed`.

Run: `.venv/Scripts/python.exe -m pytest tests/test_fuzz.py -q -p no:cacheprovider`
Expected: every fuzz test passes, including `test_a_short_dangerous_life[6]` and `[17]`. Treat any rule violation as a bug and find its cause with systematic debugging. Do not loosen the rule.

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all tests pass.

- [ ] **Step 6: Commit**

Run: `git add -A && git commit -m "feat: the lineage page (F8), relations in briefs, lineage rules and a short dangerous life"`

---

## Self-review

**Spec coverage:**

| Spec section | Where it is built |
|---|---|
| §3.1 old age | Task 1 |
| §3.2 fights | Task 2 |
| §3.3 deviation | Task 1 |
| §3.4 execution | Task 2 |
| §3.5 the moment of death | Task 1 |
| §4.1 bonds | Task 3 |
| §4.2 candidates | Task 3 |
| §5.1 inheritance | Task 4 |
| §5.2 the switch | Task 4 |
| §5.3 newcomer and new world | Tasks 1 (new world) and 4 (newcomer) |
| §6 half-strength inheritance | Task 5 |
| §7 screens | Tasks 1 (status, death screen), 3–4 (journal), 6 (F8, briefs) |
| §8 debug rules | Tasks 1 (rules 1–2) and 6 (rules 4–5); rule 3 is 4a's spouse rule, which already covers the player |
| §9 testing | every task; fuzz in Tasks 1 (`keep_playing`) and 6 |

**Differences from the spec:** the plan-time rulings 1–6 above.

**Type consistency:**
- `bonds.candidates(world, player) -> [(id, kind)]`. The same kind names are used in `succession.SILVER` and `ARTS`.
- `mortality.death_events(world, player, cause, killer, age=None, record=True)` everywhere.
- `lineage.inherited(world, knower, heir) -> [(ancestor, share)]`.

**Dry run** (the whole plan on a scratch copy of `0fb6209`: 599 passed, plus the 500-year soak deselected). It found and fixed:
- **Loading on the death screen.** `Game.load` refused a player who is nowhere; a dead player is only buried, so a dying player may load. `LineageMixin._restore` skips rebuilding for the dead, because other mixins read `place`.
- **`look`** is allowed on the death screen and shows the epitaph again.
- **Duel deaths.** A duel's own `killed` fact is the record (`record=False`), so a death in a duel is never written twice.
- **Silver.** NPCs carry a seeded purse (`silver_of`), so inheritance adds to it rather than to a missing data field.
- **Cached helpers.** `world._cached` keeps lists, so the `heir_of` lookups wrap their single values.
- **A dead player's masks stay theirs** (ruling 7). Found by the rumours-and-masks fuzz run after a death.
- **Test ordering.** The Task 1 death-screen tests check the *last* choice (a new world), because heirs and a newcomer come first from Task 4 on.
