# Phase 6c: Typed Actions and Free Talk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** With the AI on, the player types what they do, or (in a conversation) what they say. The model answers in a paragraph and proposes changes from a fixed vocabulary; the engine commits only what passes its checks. The turn waits under an animated line, and Esc lets it go.

**Architecture:**
- **`ai/validate.py`, `ai/deeds.py`, `narrate/ai_text.py`** (from the `wip-6c-deeds` draft, amended by spec §14): proposals are checked against the rules and the world, then turned into ordinary events marked `ai: true`, each with its own engine line; `check_ai` holds them to their limits.
- **`ai/intent.py`:** the two jobs (`intent`, `dialogue`) and their prompts: the state pack, the prefetch, the last paragraphs, this turn's choices, and the typed line.
- **`ai/typed.py`, `Typed`:** asks in a daemon thread, waits, lets go on Esc, and resolves the reply into a turn and the lines to show.
- **`engine/ai_turns.py`, `Game.apply_proposals`:** commits what stood, and runs at most one engine choice as if chosen.
- **`App`:**
  - routes an unknown typed line to the model;
  - draws the waiting line from the clock;
  - shows the paragraph (and, in assist mode, the engine's lines).

**Tech Stack:** Python 3.14, 6b's backends (Claude Code through the Agent SDK; OpenCode), pygame (the 30 fps redraw that already runs), pytest.

**Spec:** `docs/superpowers/specs/2026-10-01-phase6-claude-layer-design.md`: §7 and §9, as amended by §14 (written after 6b).

## Global Constraints

- **The model never writes the world.** Nothing it returns reaches the save except through `ai/validate.py`'s `accept`, then `commit`, as events marked `ai: true`.
- **No retry:**
  - rejected proposals are dropped;
  - their reasons go to the F12 overlay and the bug report.
- **Every failure changes nothing:**
  - covers a timeout, bad JSON, a schema mismatch, Esc, or a backend that cannot answer;
  - the log says "You hesitate; nothing comes of it."
- **With the AI off, a typed line costs nothing more:** today's "unknown command" path.
- **Limits:**
  - at most 4 proposals a reply;
  - a newcomer: 1 a typed line, 2 a visit, 6 a town;
  - one feeling per person a line;
  - one deed a line (ruling 11);
  - in a conversation, no `action` and no `minor_npc`.
- **Timeouts:** 30 s on Claude Code; 90 s on OpenCode.
- **No test calls a real model** except `tests/test_ai_live.py`, which is marked `live` and needs `DEEPMURIM_LIVE=1`.
- **Commits:** every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Quitting while a typed line waits:** the game closes at once and nothing is applied. Task 3 pins it with `test_quitting_while_a_typed_line_waits_closes_at_once_and_applies_nothing`.
2. **The backend logging out during a wait:** the line hesitates, and the AI says why and turns itself off (it would otherwise stay on, every later typed line silently "unknown"). Task 3 pins it with `test_logged_out_during_a_wait_the_line_hesitates_and_the_ai_says_why_and_turns_off`.
3. **An `action` that moves the player:** the turn ends in the new place, its choices those of the new place. Task 2 pins it with `test_an_action_that_travels_ends_the_turn_in_the_new_place`.
4. **A conversation's answer (or its summary) naming a stranger:**
   - the paragraph is not shown;
   - what they remember is the engine's own "They spoke with you."
   - Task 2 pins it with `test_an_answer_naming_a_stranger_is_not_shown_and_its_summary_is_the_engines`.
5. **A model that tries to break the rules** (fortunes of silver, strangers, unknown kinds, wrong types, a reply that is not JSON): nothing past the limits stands, and no invariant breaks. Task 4 pins it with `test_random_proposals_never_break_a_rule_or_the_game` and `test_random_replies_through_the_app_never_break_it`.

## Plan-time rulings (found while building, argued)

1. **The waiting line's swirl is `· • o O o •`, not `· ∘ ○ ◎ ○ ∘`:** the game's font (IBM Plex Mono) has no `∘ ○ ◎`; each renders as the missing-glyph box. *Cost if wrong:* none.
2. **A typed line let go is dimmed and marked "(let go)", not struck through:** the font has no combining long stroke either. *Cost if wrong:* none.
3. **"A visit" (2 newcomers) is a day in the town,** as the draft counted it (`made_today`). *Cost if wrong:* a long stay may meet 2 newcomers a day.
4. **A typed turn's engine lines are each event's outcome lines, never the grammar's:** `ai.toml` keeps a table per kind only so that `commit`'s narrator has one. *Cost if wrong:* none.
5. **Typed lines share narration's backend,** its pause after three failures, and its recent paragraphs (each shown paragraph joins them). *Cost if wrong:* prose failures and typed-line failures together pause the backend.
6. **A conversation's `talked` event is committed even when its paragraph is refused** (the words were said); a summary the guard refuses is replaced by "They spoke with you." *Cost if wrong:* none.
7. **A wait whose worker never answers ends at the job's timeout plus 5 s** (`GRACE`), as a failure. *Cost if wrong:* none.
8. **Task 4's two fuzz tests pass before Task 4's code:** they exercise Tasks 1-3's code, and Task 4 adds no checks of its own; the other four of its tests fail first. *Cost if wrong:* none.
9. **The `wip-6c-deeds` draft is Task 1's starting point,** with §14's changes:
   - at most 4 proposals;
   - one newcomer a line;
   - the kinds allowed per job;
   - the `talked` event;
   - an engine line for every kind;
   - `check_ai`'s town limit.

   *Cost if wrong:* none.
10. **The grammar is read once a process** (`Grammar.load` keeps each directory's tables).
    - Found by profiling the prompt, which took 15 ms of its 20 ms budget.
    - Most of that was `mcp_server.tools.View`: each one makes a `Game`, whose narrator parsed all 34 grammar files again, 12 ms a time.
    - The same cost fell on every MCP request of 6b's long-lived server.
    - The prompt now takes about 2 ms, and a `View` 0.12 ms.
    - The tables are never written after loading.

    *Cost if wrong:* a grammar file edited while the game runs is read at the next start.
11. **A deed is weighed by heaven and the dao heart by its tone, and one deed a line.**
    - Spec §14.5 names reputation, the dao heart and karma, but the draft wired only reputation.
    - The karma (5f) and heart (5e) tables count fixed kinds of event, so `ai_deed` has its own listener:
      - kind: merit 3, and a lean of +1, weight 1;
      - cruel: sin 5, and a lean of -1, weight 1;
      - bold and neutral move neither.
    - At most one deed a line, or a model could farm merit four at a time.

    *Cost if wrong:* deeds weigh more or less than intended; the numbers are tunable in `ai/deeds.py`.
12. **`check_ai` reads the model's events through a partial index** (`chronicle_ai`, added with the other optional indexes on open, so old saves gain it with no version change).
    - The dry run's soak caught it: scanning 500 years of chronicle with `json_extract` brought the whole world's check to 406 ms of its 300.
    - The town limit is counted from the same rows (`ai_arrived` per place), not by scanning entities.
    - It now takes well under 5 ms on a history of 100,000 events, and the soak passes.

    *Cost if wrong:* none.

## Files

| File | Responsibility |
|---|---|
| `ai/validate.py` | `Scene`, `Accepted`, `accept(scene, proposals, kinds)`; the vocabulary's limits. |
| `ai/deeds.py` | The events accepted proposals become, and their effects; `talked`. |
| `narrate/ai_text.py`, `narrate/grammar/ai.toml` | Each change's engine line and journal line. |
| `ai/intent.py` | The `intent` and `dialogue` jobs, their schemas and prompts. |
| `ai/typed.py` | `Typed`: start, poll, cancel, resolve. |
| `engine/ai_turns.py` | `Game.apply_proposals(events, action)`. |

Existing files touched:
- code: `debug/invariants.py`, `world/db.py`, `mcp_server/tools.py`, `narrate/outcomes.py`, `narrate/procedural.py`, `systems/attitude.py`, `systems/world_clock.py`, `engine/game.py`, `app.py`;
- docs: `docs/world-events.md`;
- tests: `tests/test_ai_live.py`.

**How each task is laid out:**
1. The tests, as whole new files.
2. The red run.
3. The new modules, as whole files.
4. One patch script, `.patches/6c_taskN.py`, holding the task's edits to existing files. Each edit asserts that its anchor matches exactly once.
5. The green run, the full suite, and the commit.

---

### Task 1: Proposals: checked, committed, held to their limits

The `wip-6c-deeds` draft, amended by spec §14 (ruling 9).

- `accept(scene, proposals, kinds)` weighs at most 4 proposals.
  - Each is checked against the rules and the world: who is here, what you carry and may give, the world's trades and traits, the body's parts.
  - It returns the events that may stand, at most one engine action, and the rest with their reasons.
- A conversation may cause neither an `action` nor a `minor_npc` (`DIALOGUE_KINDS`).
- A newcomer, and a deed, come at most once a typed line.
- The events (`ai/deeds.py`) carry `ai: true` and are the engine's own:
  - silver changes hands, and an item changes owner;
  - a person remembers;
  - a deed becomes a tale that spreads, judged by its tone: by reputation, heaven and the dao heart (ruling 11);
  - a belief is passed on, and someone new stands in the town;
  - the body is hurt, or time passes;
  - a `talked` event keeps what was said in a conversation.
- Each change has its engine line (`narrate/ai_text.py`).
- `check_ai` holds every such event to its kind's limits, reading them through a partial index (ruling 12).

**Files:**
- Create: `ai/deeds.py`
- Create: `ai/validate.py`
- Create: `narrate/ai_text.py`
- Create: `narrate/grammar/ai.toml`
- Create: `tests/test_ai_proposals.py`
- Modify (by `.patches/6c_task1.py`): `debug/invariants.py`, `mcp_server/tools.py`, `narrate/outcomes.py`, `systems/attitude.py`, `systems/world_clock.py`, `world/db.py`

**Interfaces:**
- Consumes: 6a's `ai.guard` (`NAMED`, `allowed_people`) and `mcp_server.tools`; the engine's `commit`, `Event`, `Witness`, `@effect`, `@listen`, `record_fact`, `believe`, `make_person`, `add_injury`, `advance`.
- Produces:
  - `ai.validate`: `FEELINGS`, `MAX_STRENGTH`, `MAX_DEED`, `HURTS`, `MAX_SEVERITY`, `MAX_WATCHES`, `REALMS`, `PER_VISIT`, `PER_TOWN`, `MAX_PROPOSALS`, `KINDS`, `DIALOGUE_KINDS`, `PROPOSAL`, `PROPOSALS`; `Scene(world, player, place, choices, salt)`; `Accepted(events, action, rejected)`; `accept(scene, proposals, kinds=KINDS) -> Accepted`.
  - `ai.deeds`: `KINDS`, `TONES`, `DEED_KARMA`, `DEED_HEART`; `paid`, `gave`, `felt`, `deed`, `told`, `arrived`, `hurt`, `talked(player, npc, place, summary, said)`, `waited`; `made_here`, `made_today`.
  - `mcp_server.tools.belief_handle(world, holder, fact_id)`; `debug.invariants.check_ai(world)`; the index `chronicle_ai` (`world.db.INDEXES`).

- [ ] **Step 1: Write the failing tests**

`tests/test_ai_proposals.py`:
```python
import pytest

import systems.encounters as encounters
from ai import deeds as D
from ai.validate import DIALOGUE_KINDS, MAX_PROPOSALS, PER_TOWN, Scene, accept
from debug.invariants import check_ai
from engine.actions import Action, Choice
from engine.game import Game
from engine.journal import summarize
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.events import Event, commit
from world.gen.materialize import people_at


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def scene(game, choices=(), salt="t1"):
    return Scene(game.world, game.player.id, game.place.id, list(choices), salt)


def someone(game):
    return people_at(game.world, game.place.id, exclude=game.player.id)[0]


def test_paying_moves_silver_and_never_more_than_you_have(game):
    npc, me = someone(game), game.player.id
    mine, theirs = silver_of(game.world, me), silver_of(game.world, npc.id)
    done = accept(scene(game), [{"kind": "pay", "to": npc.name, "amount": 2},
                                {"kind": "pay", "to": npc.name, "amount": mine},  # together, more than you have
                                {"kind": "pay", "to": "Nobody Here", "amount": 1}])
    assert [why for _, why in done.rejected] == ["you have not that much silver", "they are not here"]
    commit(game.world, done.events)
    assert silver_of(game.world, me) == mine - 2 and silver_of(game.world, npc.id) == theirs + 2
    assert check_ai(game.world) == []


def test_a_feeling_is_remembered_once_a_person_a_line_and_within_its_strength(game):
    npc = someone(game)
    done = accept(scene(game), [{"kind": "feeling", "who": npc.name, "feeling": "grateful", "strength": 0.4},
                                {"kind": "feeling", "who": npc.name, "feeling": "amused", "strength": 0.2},
                                {"kind": "feeling", "who": npc.name, "feeling": "adoring", "strength": 0.2}])
    assert [why for _, why in done.rejected] == ["one feeling a person a line", "no such feeling"]
    commit(game.world, done.events)
    assert any(m.feeling == "grateful" for m in game.world.memories(npc.id, about=game.player.id))
    too_strong = accept(scene(game), [{"kind": "feeling", "who": npc.name, "feeling": "fear", "strength": 0.9}])
    assert too_strong.events == [] and "strength" in too_strong.rejected[0][1]


def test_a_deed_names_only_the_known_and_becomes_a_tale(game):
    npc = someone(game)
    done = accept(scene(game), [{"kind": "deed", "text": f"You carried {npc.name}'s baskets to market.",
                                 "tone": "kind"},
                                {"kind": "deed", "text": "You bested Mo Tianlong at dice.", "tone": "bold"},
                                {"kind": "deed", "text": "You did a thing.", "tone": "sly"}])
    assert [why for _, why in done.rejected] == ["it names Mo Tianlong, whom you do not know", "no such tone"]
    commit(game.world, done.events)
    tales = game.world._conn.execute("select count(*) from facts where predicate = 'deed_kind'").fetchone()[0]
    assert tales == 1  # a tale of the world, to spread and be judged by its tone


def test_one_newcomer_a_line_and_only_of_the_worlds_trades(game):
    new = {"kind": "minor_npc", "occupation": "tea seller", "traits": ["cheerful"], "realm": "mortal"}
    done = accept(scene(game), [new, dict(new), {**new, "occupation": "astronaut"}])
    assert [why for _, why in done.rejected] == ["one newcomer a line", "no such trade"]
    before = len(people_at(game.world, game.place.id))
    commit(game.world, done.events)
    assert len(people_at(game.world, game.place.id)) == before + 1
    assert check_ai(game.world) == []


def test_hurt_and_time_stay_within_their_limits(game):
    start = game.world.time
    done = accept(scene(game), [{"kind": "hurt", "location": "left arm", "injury": "cut", "severity": 1},
                                {"kind": "hurt", "location": "left arm", "injury": "cut", "severity": 5},
                                {"kind": "time", "watches": 2}, {"kind": "time", "watches": 40}])
    assert len(done.events) == 2 and len(done.rejected) == 2
    commit(game.world, done.events)
    assert game.world.time == start + 2 and any(i.location == "left arm" for i in game.body().injuries)


def test_an_action_must_be_one_of_this_turns_choices(game):
    rest = Choice("Rest a while", Action("rest"))
    done = accept(scene(game, [rest]), [{"kind": "action", "choice": "Rest a while"},
                                        {"kind": "action", "choice": "Fly to the moon"}])
    assert done.action == Action("rest") and done.rejected[0][1] == "no such choice now"


def test_talk_proposes_no_action_and_no_newcomer(game):
    rest = Choice("Rest a while", Action("rest"))
    done = accept(scene(game, [rest]), [{"kind": "action", "choice": "Rest a while"},
                                        {"kind": "minor_npc", "occupation": "tea seller", "traits": ["cheerful"]}],
                  kinds=DIALOGUE_KINDS)
    assert done.action is None and [why for _, why in done.rejected] == ["not while talking"] * 2


def test_at_most_four_proposals_are_weighed(game):
    many = [{"kind": "time", "watches": 1}] * (MAX_PROPOSALS + 2)
    done = accept(scene(game), many)
    assert len(done.events) == MAX_PROPOSALS and [why for _, why in done.rejected] == ["too many changes"] * 2


def test_what_was_talked_of_is_remembered_and_summarised(game):
    npc, me = someone(game), game.player.id
    commit(game.world, [D.talked(me, npc.id, game.place.id, "You asked after the bandits on the marsh road.",
                                 "Any news of bandits?")])
    memory = [m for m in game.world.memories(npc.id, about=me) if m.event.kind == "talked"]
    assert memory and "bandits on the marsh road" in summarize(game.world, memory[-1].event)
    assert check_ai(game.world) == []


def test_every_accepted_change_has_its_engine_line(game):
    npc = someone(game)
    done = accept(scene(game), [{"kind": "feeling", "who": npc.name, "feeling": "grateful", "strength": 0.3},
                                {"kind": "time", "watches": 1}])
    lines = game._commit(done.events)
    assert f"{npc.name} is grateful." in [t for t, _ in lines] and "A watch passes." in [t for t, _ in lines]


def test_check_ai_finds_a_change_past_its_limits(game):
    npc = someone(game)
    commit(game.world, [Event("ai_felt", (game.player.id, npc.id), game.place.id,
                              {"feeling": "fear", "strength": 0.9, "ai": True, "proposal": {}})])
    commit(game.world, [Event("parted", (game.player.id, npc.id), game.place.id, {"ai": True})])
    problems = check_ai(game.world)
    assert any("feeling past its limits" in p for p in problems)
    assert any("of no proposal kind" in p for p in problems)


def test_a_town_takes_at_most_six_newcomers(game):
    town = game.place.id
    game.world.update_data(town, ai_people=PER_TOWN)
    done = accept(scene(game), [{"kind": "minor_npc", "occupation": "tea seller", "traits": ["cheerful"]}])
    assert done.rejected[0][1] == "enough newcomers here for now"


def test_a_deed_is_weighed_by_heaven_and_the_heart_by_its_tone(game):
    from systems.heart import heart_of
    from systems.karma import karma_of
    world, me = game.world, game.player.id
    merit, lean = karma_of(world, me)["merit"], heart_of(world, me)["lean"]
    commit(world, accept(scene(game), [{"kind": "deed", "text": "You fed a starving beggar.", "tone": "kind"}]).events)
    assert karma_of(world, me)["merit"] > merit and heart_of(world, me)["lean"] > lean
    sin, lean = karma_of(world, me)["sin"], heart_of(world, me)["lean"]
    commit(world, accept(scene(game), [{"kind": "deed", "text": "You kicked a beggar.", "tone": "cruel"}]).events)
    assert karma_of(world, me)["sin"] > sin and heart_of(world, me)["lean"] < lean


def test_one_deed_a_line(game):
    done = accept(scene(game), [{"kind": "deed", "text": "You helped an old woman.", "tone": "kind"},
                                {"kind": "deed", "text": "You helped another.", "tone": "kind"}])
    assert len(done.events) == 1 and [why for _, why in done.rejected] == ["one deed a line"]


def test_check_ai_reads_only_the_models_events_however_long_the_history(game):
    import gc
    import time
    world = game.world
    with world.transaction():
        world._conn.executemany("insert into chronicle(time, kind, actors, place, data) values (?, ?, ?, ?, ?)",
                                [(0, "rested", "[]", None, '{"days": 1}')] * 100_000)
    commit(world, accept(scene(game), [{"kind": "time", "watches": 1}]).events)
    check_ai(world)
    gc.collect()
    best = float("inf")
    for _ in range(5):
        began = time.perf_counter()
        check_ai(world)
        best = min(best, time.perf_counter() - began)
    assert best < 0.005  # the soak's check of the whole world has 0.3 s for everything
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_proposals.py`
Expected: a collection error, `ImportError: cannot import name 'deeds' from 'ai'`.

- [ ] **Step 3: Write the new modules**

`ai/deeds.py`:
```python
"""What Claude's accepted proposals become (phase 6 spec 7.4, 14.5): ordinary events, each marked `ai: true`.

Nothing here decides whether a proposal may stand; `ai/validate.py` does, and builds these events. Their effects
are the engine's own: silver changes hands, an item changes owner, a person remembers, a deed is told, a belief is
passed on, someone new stands in the town, the body is hurt, time passes.
"""

from systems.beliefs import believe
from systems.bodies import load_body, save_body
from systems.facts import make_variant, place_name, record_fact
from systems.founding import make_person
from systems.purse import silver_of
from systems.time import advance
from world.body import add_injury
from world.events import Event, Witness, effect, listen

KINDS = frozenset({"ai_paid", "ai_gave", "ai_felt", "ai_deed", "ai_told", "ai_arrived", "ai_hurt", "ai_waited",
                   "talked"})
TONES = ("kind", "cruel", "neutral", "bold")
DEED_WEIGHT = 1.0
# A told deed weighs little (spec 14.5): heaven counts it as a small kindness or cruelty (healing is 5), and the
# dao heart leans by it with the least weight. Bold and neutral deeds move neither.
DEED_KARMA = {"kind": ("merit", 3), "cruel": ("sin", 5)}
DEED_HEART = {"kind": (1, 1), "cruel": (-1, 1)}


def paid(player: int, npc: int, place: int, amount: int, proposal: dict) -> Event:
    return Event("ai_paid", (player, npc), place, {"amount": amount, "ai": True, "proposal": proposal})


def gave(player: int, npc: int, place: int, item: int, proposal: dict) -> Event:
    return Event("ai_gave", (player, npc), place, {"item": item, "ai": True, "proposal": proposal})


def felt(player: int, npc: int, place: int, feeling: str, strength: float, proposal: dict) -> Event:
    return Event("ai_felt", (player, npc), place, {"feeling": feeling, "strength": strength, "ai": True,
                                                    "proposal": proposal},
                 witnesses=(Witness(npc, feeling, strength),))


def deed(player: int, people: tuple, place: int, text: str, tone: str, proposal: dict) -> Event:
    return Event("ai_deed", (player, *people), place, {"text": text, "tone": tone, "ai": True, "proposal": proposal})


def told(npc: int, player: int, place: int, fact: int, proposal: dict) -> Event:
    return Event("ai_told", (npc, player), place, {"fact": fact, "ai": True, "proposal": proposal})


def arrived(player: int, place: int, path: str, occupation: str, traits: list, realm: str, proposal: dict) -> Event:
    return Event("ai_arrived", (player,), place, {"path": path, "occupation": occupation, "traits": list(traits),
                                                  "realm": realm, "ai": True, "proposal": proposal})


def hurt(player: int, place: int, location: str, kind: str, severity: int, proposal: dict) -> Event:
    return Event("ai_hurt", (player,), place, {"location": location, "kind": kind, "severity": severity, "ai": True,
                                               "proposal": proposal})


def talked(player: int, npc: int, place: int, summary: str, said: str) -> Event:
    """A line said in a conversation and its answer (spec 14.4): they remember it, as the summary tells it."""
    return Event("talked", (player, npc), place, {"summary": summary[:200], "said": said[:200], "ai": True},
                 witnesses=(Witness(npc, "engaged", 0.2),))


def waited(player: int, place: int, watches: int, proposal: dict) -> Event:
    return Event("ai_waited", (player,), place, {"watches": watches, "ai": True, "proposal": proposal})


@effect("ai_paid")
def _paid(world, event) -> None:
    player, npc = event.actors
    amount = event.data["amount"]
    world.update_data(player, silver=silver_of(world, player) - amount)
    world.update_data(npc, silver=silver_of(world, npc) + amount)


@effect("ai_gave")
def _gave(world, event) -> None:
    player, npc = event.actors
    world.unrelate(player, "owns", event.data["item"])
    world.relate(npc, event.data["item"], "owns")


@effect("ai_told")
def _told(world, event) -> None:
    npc, player = event.actors
    found = next(((b, f) for b, f in world.known_facts(npc) if f.id == event.data["fact"]), None)
    if found is not None:
        belief, _ = found
        believe(world, player, belief.fact_id, belief.variant, npc, belief.confidence * 0.9, belief.hops + 1, "told")


@effect("ai_arrived")
def _arrived(world, event) -> None:
    d = event.data
    make_person(world, d["path"], event.place, occupation=d["occupation"], traits=list(d["traits"]),
                realm=d["realm"], ai_made=True)
    world.update_data(event.place, ai_people=made_here(world, event.place) + 1,
                      ai_people_today=[world.time // 4, made_today(world, event.place) + 1])


def made_here(world, town: int) -> int:
    """How many people Claude has brought into this town."""
    return int(world.entity(town).data.get("ai_people", 0))


def made_today(world, town: int) -> int:
    """How many of them came today (a visit, plan ruling)."""
    mark = world.entity(town).data.get("ai_people_today") or [None, 0]
    return mark[1] if mark[0] == world.time // 4 else 0


@effect("ai_hurt")
def _hurt(world, event) -> None:
    d = event.data
    body = load_body(world, event.actors[0])
    add_injury(body, d["location"], d["kind"], d["severity"], world.time, "what you did")
    save_body(world, event.actors[0], body)


@effect("ai_waited")
def _waited(world, event) -> None:
    advance(world, event.data["watches"])


@listen("ai_deed")
def _deed_weighed(world, event, event_id: int) -> None:
    """Heaven (5f) and the dao heart (5e) weigh a deed by its tone."""
    from systems import heart, karma
    tone = event.data["tone"]
    if tone in DEED_KARMA:
        side, amount = DEED_KARMA[tone]
        karma.add(world, event.actors[0], **{side: amount})
    if tone in DEED_HEART:
        heart.deed(world, event.actors[0], *DEED_HEART[tone])


@listen("ai_deed")
def _deed_told(world, event, event_id: int) -> None:
    """A deed is a tale like any other: it spreads, and is judged by its tone."""
    player, d = event.actors[0], event.data
    variant = {**make_variant(f"deed_{d['tone']}", player, None, place=place_name(world, event.place)),
               "text": d["text"]}
    record_fact(world, player, f"deed_{d['tone']}", None, place=event.place, source_event=event_id,
                weight=DEED_WEIGHT, variant=variant)
```

`ai/validate.py`:
```python
"""Claude's proposals checked against the rules and the world (phase 6 spec 7.4), turned into events.

`accept(scene, proposals, kinds)` takes the model's list and returns what may stand (events, at most one engine
action) and what may not (each with its reason, for the debug overlay; there is no retry, spec 14.5). It never
writes: the caller commits the events. The checks are the hard limits; the model is told the soft ones (its state
pack) and is expected to keep to them.
"""

from dataclasses import dataclass, field

import ai.deeds as D
from ai.guard import NAMED, allowed_people
from engine.actions import Action
from mcp_server.tools import belief_handle
from systems.purse import silver_of
from world.body import BODY_PARTS
from world.gen.materialize import people_at
from world.db import World
from world.gen.npc import OCCUPATIONS, TRAITS

FEELINGS = ("grateful", "amused", "respect", "annoyed", "contempt", "fear")
MAX_STRENGTH = 0.5
MAX_DEED = 120
HURTS = ("bruise", "cut", "burn", "fracture")
MAX_SEVERITY = 2
MAX_WATCHES = 8
REALMS = ("mortal", "third-rate")
PER_VISIT, PER_TOWN = 2, 6  # newcomers: a visit is a day in the town (plan ruling)
MAX_PROPOSALS = 4
KINDS = ("action", "pay", "give", "feeling", "deed", "tell", "minor_npc", "hurt", "time")
DIALOGUE_KINDS = tuple(k for k in KINDS if k not in ("action", "minor_npc"))  # talking, not acting (spec 14.4)

# One flat item schema for every kind (the CLI's structured output wants one shape); `accept` checks each kind's
# own fields.
PROPOSAL = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": list(KINDS)},
        "choice": {"type": "string", "maxLength": 120},
        "to": {"type": "string", "maxLength": 60}, "who": {"type": "string", "maxLength": 60},
        "amount": {"type": "integer"}, "item": {"type": "string", "maxLength": 80},
        "feeling": {"type": "string", "maxLength": 20}, "strength": {"type": "number"},
        "text": {"type": "string", "maxLength": 200}, "tone": {"type": "string", "maxLength": 10},
        "handle": {"type": "string", "maxLength": 20},
        "occupation": {"type": "string", "maxLength": 40},
        "traits": {"type": "array", "items": {"type": "string", "maxLength": 20}, "maxItems": 2},
        "realm": {"type": "string", "maxLength": 20},
        "location": {"type": "string", "maxLength": 20}, "injury": {"type": "string", "maxLength": 20},
        "severity": {"type": "integer"}, "watches": {"type": "integer"},
    },
    "required": ["kind"],
    "additionalProperties": False,
}
PROPOSALS = {"type": "array", "items": PROPOSAL, "maxItems": MAX_PROPOSALS}


@dataclass
class Scene:
    """What a turn's proposals are judged against."""
    world: World
    player: int
    place: int
    choices: list            # this turn's valid choices (shown and folded): `action` must name one
    salt: str                # seeds a minor NPC (the same turn, the same person)


@dataclass
class Accepted:
    events: list = field(default_factory=list)
    action: Action | None = None
    rejected: list = field(default_factory=list)   # (proposal, reason)


def _here(scene: Scene) -> dict[str, int]:
    found: dict[str, list[int]] = {}
    for person in people_at(scene.world, scene.place, exclude=scene.player):
        found.setdefault(person.name.lower(), []).append(person.id)
    return {name: ids[0] for name, ids in found.items() if len(ids) == 1}


def _someone(scene: Scene, name) -> int | None:
    return _here(scene).get(str(name or "").strip().lower())


def _item(scene: Scene, name) -> int | None:
    world, wanted = scene.world, str(name or "").strip().lower()
    held = set(world.targets(scene.player, "wields")) | set(world.targets(scene.player, "wears"))
    for item in world.targets(scene.player, "owns"):
        entity = world.entity(item)
        if entity is None or entity.name.lower() != wanted or entity.data.get("used"):
            continue
        if item in held or entity.data.get("armoury") is not None or entity.data.get("claimed_by") is not None:
            return None  # what is wielded, worn or a sect's is not yours to hand over
        return item
    return None


def check(scene: Scene, p: dict, done: Accepted, felt: set) -> tuple[object, str | None]:
    """(an event or an Action, None) if it may stand; (None, the reason) if not."""
    world, me, here = scene.world, scene.player, scene.place
    kind = p.get("kind")
    if kind == "action":
        choice = next((c for c in scene.choices if c.label == p.get("choice")), None)
        if choice is None:
            return None, "no such choice now"
        if done.action is not None:
            return None, "only one action a turn"
        return choice.action, None
    if kind == "pay":
        npc, amount = _someone(scene, p.get("to")), p.get("amount")
        if npc is None:
            return None, "they are not here"
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            return None, "no such sum"
        spent = sum(e.data["amount"] for e in done.events if e.kind == "ai_paid")
        if amount + spent > silver_of(world, me):
            return None, "you have not that much silver"
        return D.paid(me, npc, here, amount, p), None
    if kind == "give":
        npc, item = _someone(scene, p.get("to")), _item(scene, p.get("item"))
        if npc is None:
            return None, "they are not here"
        if item is None or any(e.kind == "ai_gave" and e.data["item"] == item for e in done.events):
            return None, "you have no such thing to give"
        return D.gave(me, npc, here, item, p), None
    if kind == "feeling":
        npc, feeling, strength = _someone(scene, p.get("who")), p.get("feeling"), p.get("strength", 0.3)
        if npc is None:
            return None, "they are not here"
        if feeling not in FEELINGS:
            return None, "no such feeling"
        if not isinstance(strength, (int, float)) or not 0 < strength <= MAX_STRENGTH:
            return None, f"a feeling's strength is above 0 and at most {MAX_STRENGTH}"
        if npc in felt:
            return None, "one feeling a person a line"
        felt.add(npc)
        return D.felt(me, npc, here, feeling, float(strength), p), None
    if kind == "deed":
        text, tone = str(p.get("text") or "").strip(), p.get("tone")
        if not text or len(text) > MAX_DEED:
            return None, f"a deed is told in at most {MAX_DEED} characters"
        if tone not in D.TONES:
            return None, "no such tone"
        known = allowed_people(world, me, here)
        for found in NAMED.findall(text):
            if not any(found in name or name in found for name in known):
                return None, f"it names {found}, whom you do not know"
        if any(e.kind == "ai_deed" for e in done.events):
            return None, "one deed a line"  # deeds weigh on karma: one a line, or merit could be farmed
        people = tuple(sorted({pid for name, pid in _here(scene).items() if name in text.lower()}))
        return D.deed(me, people, here, text, tone, p), None
    if kind == "tell":
        npc, handle = _someone(scene, p.get("who")), p.get("handle")
        if npc is None:
            return None, "they are not here"
        fact = next((f.id for _, f in world.known_facts(npc) if belief_handle(world, npc, f.id) == handle), None)
        if fact is None:
            return None, "they hold no such belief"
        return D.told(npc, me, here, fact, p), None
    if kind == "minor_npc":
        occupation, traits, realm = p.get("occupation"), list(p.get("traits") or []), p.get("realm", "mortal")
        if occupation not in OCCUPATIONS:
            return None, "no such trade"
        if not traits or any(t not in TRAITS for t in traits):
            return None, "no such traits"
        if realm not in REALMS:
            return None, "a newcomer is a mortal or third-rate"
        new = sum(1 for e in done.events if e.kind == "ai_arrived")
        if new:
            return None, "one newcomer a line"
        if D.made_today(world, here) >= PER_VISIT or D.made_here(world, here) >= PER_TOWN:
            return None, "enough newcomers here for now"
        return D.arrived(me, here, f"ai:{here}:{scene.salt}:{new}", occupation, traits, realm, p), None
    if kind == "hurt":
        location, injury, severity = p.get("location"), p.get("injury"), p.get("severity")
        if location not in BODY_PARTS or injury not in HURTS:
            return None, "no such hurt"
        if not isinstance(severity, int) or isinstance(severity, bool) or not 1 <= severity <= MAX_SEVERITY:
            return None, f"a hurt is of severity 1 to {MAX_SEVERITY}"
        return D.hurt(me, here, location, injury, severity, p), None
    if kind == "time":
        watches = p.get("watches")
        if not isinstance(watches, int) or isinstance(watches, bool) or not 1 <= watches <= MAX_WATCHES:
            return None, f"time passes in 1 to {MAX_WATCHES} watches"
        return D.waited(me, here, watches, p), None
    return None, "no such kind of proposal"


def accept(scene: Scene, proposals: list, kinds: tuple = KINDS) -> Accepted:
    done, felt, weighed = Accepted(), set(), 0
    for p in proposals if isinstance(proposals, list) else []:
        if not isinstance(p, dict):
            continue
        if weighed >= MAX_PROPOSALS:
            result, why = None, "too many changes"
        elif p.get("kind") in KINDS and p.get("kind") not in kinds:
            result, why = None, "not while talking"
        else:
            weighed += 1
            result, why = check(scene, p, done, felt)
        if why is not None:
            done.rejected.append((p, why))
        elif isinstance(result, Action):
            done.action = result
        else:
            done.events.append(result)
    return done
```

`narrate/ai_text.py`:
```python
"""What the player is told of what the model's accepted proposals did (phase 6c, spec 14.6): the engine's own
short line for each change, shown under the model's paragraph in assist mode, and the journal's lines. A deed is a
rumour like any other."""

from narrate.outcomes import cap, outcome, summary  # first: outcomes loads gossip_text, which needs it loaded
from narrate.gossip_text import SPECIAL_PHRASES, who

from ai.deeds import TONES


def _name(world, entity_id) -> str:
    entity = world.entity(entity_id) if isinstance(entity_id, int) else None
    return entity.name if entity else "someone"


# --- rumours ---------------------------------------------------------------------------------------------------

def _deed(world, v, viewer) -> str:
    teller = who(world, v.get("actor"), viewer)
    return cap(f"{teller}: {v.get('text', 'a deed').rstrip('.')}" + (f", in {v['place']}." if v.get("place") else "."))


for _tone in TONES:
    SPECIAL_PHRASES[f"deed_{_tone}"] = _deed


# --- outcomes --------------------------------------------------------------------------------------------------

@outcome("ai_paid", body_facts=False)
def _paid(world, event):
    return [f"{cap(_name(world, event.actors[1]))} takes {event.data['amount']} silver from you."], {}


@summary("ai_paid")
def _paid_line(world, entry, names, place, other):
    return f"Paid {entry.data['amount']} silver to {_name(world, entry.actors[1])} in {place}."


@outcome("ai_gave", body_facts=False)
def _gave(world, event):
    return [f"{cap(_name(world, event.actors[1]))} now holds {_name(world, event.data['item'])}."], {}


@summary("ai_gave")
def _gave_line(world, entry, names, place, other):
    return f"Gave {_name(world, entry.data['item'])} to {_name(world, entry.actors[1])} in {place}."


FELT = {"grateful": "is grateful", "amused": "is amused", "respect": "respects you", "annoyed": "is annoyed",
        "contempt": "holds you in contempt", "fear": "fears you"}


@outcome("ai_felt", body_facts=False)
def _felt(world, event):
    return [f"{cap(_name(world, event.actors[1]))} {FELT.get(event.data['feeling'], 'remembers it')}."], {}


@summary("ai_felt")
def _felt_line(world, entry, names, place, other):
    return f"Left {_name(world, entry.actors[1])} {entry.data['feeling']} in {place}."


@outcome("ai_deed", body_facts=False)
def _deed_done(world, event):
    return [f"It may be told: {event.data['text'].rstrip('.')}."], {}


@summary("ai_deed")
def _deed_line(world, entry, names, place, other):
    return f"{entry.data['text'].rstrip('.')} ({place})."


@outcome("ai_told", body_facts=False)
def _told(world, event):
    return [f"You learn what {_name(world, event.actors[0])} holds to be so."], {}


@summary("ai_told")
def _told_line(world, entry, names, place, other):
    return f"Heard something from {_name(world, entry.actors[0])} in {place}."


@outcome("ai_arrived", body_facts=False)
def _arrived(world, event):
    return [f"A {event.data['occupation']} is here now."], {}


@summary("ai_arrived")
def _arrived_line(world, entry, names, place, other):
    return f"Met a {entry.data['occupation']} in {place}."


@outcome("ai_hurt", body_facts=False)
def _hurt(world, event):
    d = event.data
    done = {"bruise": "bruised", "cut": "cut", "burn": "burned", "fracture": "fractured"}.get(d["kind"], "hurt")
    return [f"Your {d['location']} is {done}."], {}


@summary("ai_hurt")
def _hurt_line(world, entry, names, place, other):
    return f"Hurt your {entry.data['location']} in {place}."


@outcome("ai_waited", body_facts=False)
def _waited(world, event):
    n = event.data["watches"]
    return ["A watch passes." if n == 1 else f"{n} watches pass."], {}


@outcome("talked", body_facts=False)
def _talked(world, event):
    return [], {}  # the answer itself is the turn's text


@summary("talked")
def _talked_line(world, entry, names, place, other):
    return f"Talked with {_name(world, entry.actors[1])} in {place}: {entry.data['summary'].rstrip('.')}."


@summary("ai_waited")
def _waited_line(world, entry, names, place, other):
    return f"Spent {entry.data['watches']} watch{'es' if entry.data['watches'] != 1 else ''} in {place}."
```

`narrate/grammar/ai.toml`:
```toml
# The AI layer (phase 6c): what Claude's accepted proposals did. Claude's prose tells the moment; these are the
# engine's own quiet frame for it.

[symbols]
ai_air = ["The moment passes.", "Somewhere a door creaks shut.", "The wind shifts.", "A dog barks, far off.", "The light moves on the wall.", "Life in the town goes on."]

[ai_paid]
colour = "dim"
lines = ["#ai_air#"]

[ai_gave]
colour = "dim"
lines = ["#ai_air#"]

[ai_felt]
colour = "dim"
lines = ["#ai_air#"]

[ai_deed]
colour = "dim"
lines = ["#ai_air#"]

[ai_told]
colour = "dim"
lines = ["#ai_air#"]

[ai_arrived]
colour = "dim"
lines = ["#ai_air#"]

[ai_hurt]
colour = "dim"
lines = ["#ai_air#"]

[ai_waited]
colour = "dim"
lines = ["#ai_air#"]

[talked]
colour = "dim"
lines = ["#ai_air#"]
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/6c_task1.py`:
```python
"""Task 1's edits to existing files. Each edit replaces one exact anchor and stops if it is not found once."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"{path}: the anchor is found {text.count(old)} times: {old[:60]!r}"
    p.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")

edit('debug/invariants.py', r'''    problems += check_alchemy_world(world)
    problems += check_crafts(world)
''', r'''    problems += check_alchemy_world(world)
    problems += check_ai(world)
    problems += check_crafts(world)
''')

edit('debug/invariants.py', r'''            out.append(f"#{person} knows a recipe at mastery {value}")
    return out
''', r'''            out.append(f"#{person} knows a recipe at mastery {value}")
    return out


def check_ai(world) -> list[str]:
    """Every event the model's proposals made is of the vocabulary and within its limits (phase 6 spec 9, 14.7)."""
    import json

    import ai.validate as V
    from ai.deeds import KINDS
    out, arrivals = [], {}
    # Through the partial index `chronicle_ai`: the WHERE must stay exactly its own.
    rows = world._conn.execute("select id, kind, place, data from chronicle where json_extract(data, '$.ai') = 1")
    for event_id, kind, place, raw in rows:
        d = json.loads(raw)
        if kind == "ai_arrived":
            arrivals[place] = arrivals.get(place, 0) + 1
        if kind not in KINDS:
            out.append(f"event #{event_id} ({kind}) is marked as Claude's but is of no proposal kind")
        elif kind == "ai_felt" and (d["feeling"] not in V.FEELINGS or not 0 < d["strength"] <= V.MAX_STRENGTH):
            out.append(f"event #{event_id} leaves a feeling past its limits")
        elif kind == "ai_hurt" and not 1 <= d["severity"] <= V.MAX_SEVERITY:
            out.append(f"event #{event_id} hurts past its limits")
        elif kind == "ai_waited" and not 1 <= d["watches"] <= V.MAX_WATCHES:
            out.append(f"event #{event_id} passes time past its limits")
        elif kind == "ai_paid" and d["amount"] <= 0:
            out.append(f"event #{event_id} pays nothing")
        elif kind == "talked" and not isinstance(d.get("summary"), str):
            out.append(f"event #{event_id} is a talk with no summary")
    for town, made in arrivals.items():
        if made > V.PER_TOWN:
            out.append(f"town #{town} has {made} newcomers the model made, past {V.PER_TOWN}")
    return out
''')

edit('mcp_server/tools.py', r'''        raw = f"{self.world.world_seed}:{holder}:{fact_id}".encode()
        return "b" + hashlib.sha256(raw).hexdigest()[:10]
''', r'''        return belief_handle(self.world, holder, fact_id)


def belief_handle(world, holder: int, fact_id: int) -> str:
    """A belief's opaque name: what Claude passes back to `tell` it (phase 6b validates it the same way)."""
    raw = f"{world.world_seed}:{holder}:{fact_id}".encode()
    return "b" + hashlib.sha256(raw).hexdigest()[:10]
''')

edit('narrate/outcomes.py', r'''import narrate.karma_text  # noqa: E402,F401
import systems.price_events  # noqa: E402,F401  (registers price events)
''', r'''import narrate.karma_text  # noqa: E402,F401
import narrate.ai_text  # noqa: E402,F401  (phase 6b: what Claude's proposals did)
import systems.price_events  # noqa: E402,F401  (registers price events)
''')

edit('systems/attitude.py', r'''    "annoyed": -0.4, "contempt": -0.3, "humiliated": -0.8, "hatred": -1.5, "grief": -1.5, "wronged": -1.2,
}
''', r'''    "annoyed": -0.4, "contempt": -0.3, "humiliated": -0.8, "hatred": -1.5, "grief": -1.5, "wronged": -1.2,
    "fear": -0.5,  # phase 6b: one Claude may leave in someone
}
''')

edit('systems/attitude.py', r'''    "enslaved": -0.8,  # phase 5c: a control pill forced on someone
}
''', r'''    "enslaved": -0.8,  # phase 5c: a control pill forced on someone
    "deed_kind": 0.3, "deed_cruel": -0.6, "deed_bold": 0.1, "deed_neutral": 0.0,  # phase 6b: a deed told by its tone
}
''')

edit('systems/world_clock.py', r'''import systems.karma_world  # noqa: E402,F401  phase 5f: heaven's retribution, a sinner's luck, temples
''', r'''import systems.karma_world  # noqa: E402,F401  phase 5f: heaven's retribution, a sinner's luck, temples
import ai.deeds  # noqa: E402,F401  phase 6b: what Claude's accepted proposals become
''')

edit('world/db.py', r'''    "create index if not exists facts_predicate on facts(predicate)",  # 4e: the newest lists a town has heard
)
''', r'''    "create index if not exists facts_predicate on facts(predicate)",  # 4e: the newest lists a town has heard
    # 6c: the model's events alone (check_ai reads them every turn; the chronicle grows for centuries)
    "create index if not exists chronicle_ai on chronicle(id) where json_extract(data, '$.ai') = 1",
)
''')

print("task 1 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/6c_task1.py`
Expected: `task 1 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_proposals.py`
Expected: `15 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow and live ones are deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: proposals - checked against the rules and the world, committed as ordinary events, held to their limits

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 2: Typed actions and talk: the two jobs, the wait, the turn

- `ai/intent.py` holds the `intent` and `dialogue` jobs, their schemas and system prompts.
  - The vocabulary is told to the model with its limits.
  - The prompts carry the state pack, the prefetch, the last paragraphs, this turn's choices, and the typed line; a conversation adds the person and its last 8 lines.
- `ai/typed.py`'s `Typed` asks in a daemon thread.
  - It waits: 30 s on Claude Code, 90 s on OpenCode, with a 5 s grace (ruling 7).
  - It lets go on `cancel`.
  - `resolve` checks the proposals and commits what stands through `Game.apply_proposals`, which also runs at most one engine choice as if chosen.
  - It says what to show: the paragraph, then the engine's lines unless the mode is AI only.
  - A paragraph the guard refuses gives way to the engine's lines and "You try, but it does not go as you meant."
  - Any failure changes nothing and says "You hesitate".
- The grammar is read once a process (ruling 10).

**Files:**
- Create: `ai/intent.py`
- Create: `ai/typed.py`
- Create: `engine/ai_turns.py`
- Create: `tests/test_ai_typed.py`
- Modify (by `.patches/6c_task2.py`): `engine/game.py`, `narrate/procedural.py`

**Interfaces:**
- Consumes: Task 1's `accept`, `Scene`, `KINDS`, `DIALOGUE_KINDS`, `PROPOSALS`, `talked`; 6b's backends (`call(job, prompt)`, `name`, `paused()`), `build_prefetch`; 6a's `Narration` (`bridge`, `mode`, `recent`, `unavailable()`), `build_pack`, `refusal`, `unwrap`.
- Produces:
  - `ai.intent`: `MODEL`, `TIMEOUTS`, `DEFAULT_TIMEOUT`, `TALK_LINES`, `INTENT_SCHEMA`, `DIALOGUE_SCHEMA`, `VOCABULARY`, `INTENT_SYSTEM`, `DIALOGUE_SYSTEM`; `timeout_for(bridge)`, `intent_job(timeout)`, `dialogue_job(timeout)`, `intent_prompt(game, typed, choices, recent)`, `dialogue_prompt(game, typed, person, talk, recent)`.
  - `ai.typed`: `GRACE`, `HESITATE`, `AMISS`, `Waiting`; `Typed(narration, clock)` with `ready()`, `start(game, typed, choices)`, `poll() -> (Waiting, reply) | None`, `cancel() -> Waiting | None`, `resolve(game, waiting, reply, choices, mode) -> (Turn | None, lines)`, and `waiting`, `talk`, `last`.
  - `Game.apply_proposals(events, action=None) -> Turn` (`engine/ai_turns.py`, `AiTurnsMixin`).

- [ ] **Step 1: Write the failing tests**

`tests/test_ai_typed.py`:
```python
import gc
import time

import pytest

import systems.encounters as encounters
from ai.fake import FakeClaude
from ai.intent import DIALOGUE_SCHEMA, INTENT_SCHEMA, dialogue_prompt, intent_prompt, timeout_for
from ai.narrate import Narration
from ai.typed import AMISS, HESITATE, Typed
from ai.validate import Scene, accept
from mcp_server.tools import View
from engine.actions import Action, Choice
from engine.game import Game
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.gen.materialize import people_at


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def someone(game):
    return people_at(game.world, game.place.id, exclude=game.player.id)[0]


def typed(*replies, mode="assist"):
    fake = FakeClaude(*replies)
    return Typed(Narration(fake, mode)), fake


def answer(t: Typed, wait: float = 5.0):
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        got = t.poll()
        if got is not None:
            return got
        time.sleep(0.01)
    raise AssertionError("no answer")


def test_the_intent_prompt_carries_the_state_the_people_the_choices_and_the_line(game):
    rest = Choice("Rest a while", Action("rest"))
    prompt = intent_prompt(game, "I sit by the well.", [rest], ["You arrived at dusk."])
    for part in ("STATE:", "PEOPLE HERE:", "- Rest a while", "You arrived at dusk.", "THE PLAYER TYPES: I sit by"):
        assert part in prompt
    assert f"TALKING TO: {someone(game).name}" in dialogue_prompt(game, "Hello.", someone(game).id, [], [])


def test_each_backend_waits_its_own_time():
    class Door:
        name = "OpenCode"
    assert timeout_for(Door()) == 90.0 and timeout_for(FakeClaude()) == 30.0


def test_a_typed_action_commits_what_stands_and_shows_the_paragraph_then_the_engine_lines(game):
    npc, me = someone(game), game.player.id
    mine = silver_of(game.world, me)
    t, fake = typed({"prose": f"You buy {npc.name} a cup of tea.", "proposals": [
        {"kind": "pay", "to": npc.name, "amount": 1}, {"kind": "pay", "to": "Nobody", "amount": 1}]})
    t.start(game, "I buy the tea seller a cup of tea.", [])
    assert fake.calls[0][0] == "intent" and "THE PLAYER TYPES" in fake.calls[0][1]
    w, reply = answer(t)
    turn, lines = t.resolve(game, w, reply, [], "assist")
    assert silver_of(game.world, me) == mine - 1
    assert lines[0] == (f"You buy {npc.name} a cup of tea.", "prose")
    assert (f"{npc.name} takes 1 silver from you.", "dim") in lines
    assert t.last["rejected"][0][1] == "they are not here" and t.last["refused"] is None
    assert t.narration.recent[-1] == lines[0][0]


def test_in_ai_only_the_paragraph_alone_is_shown(game):
    npc = someone(game)
    t, _ = typed({"prose": "You bow.", "proposals": [{"kind": "feeling", "who": npc.name, "feeling": "respect"}]},
                 mode="ai_only")
    t.start(game, "I bow.", [])
    w, reply = answer(t)
    _, lines = t.resolve(game, w, reply, [], "ai_only")
    assert lines == [("You bow.", "prose")]
    assert any(m.feeling == "respect" for m in game.world.memories(npc.id, about=game.player.id))


def test_an_action_runs_the_engines_choice_as_if_chosen(game):
    rest = Choice("Rest a while", Action("rest"))
    t, _ = typed({"prose": "You find a quiet bench.", "proposals": [{"kind": "action", "choice": "Rest a while"}]})
    t.start(game, "I take a rest.", [rest])
    start = game.world.time
    w, reply = answer(t)
    turn, lines = t.resolve(game, w, reply, [rest], "assist")
    assert game.world.time > start and len(lines) > 1 and turn.narrated  # the rest's own lines follow


def test_a_paragraph_telling_what_did_not_happen_gives_way_to_the_engines_lines(game):
    npc = someone(game)
    t, _ = typed({"prose": f"You hand {npc.name} 777 silver.", "proposals": [
        {"kind": "pay", "to": npc.name, "amount": 10 ** 9}, {"kind": "time", "watches": 1}]})
    t.start(game, "I pay a fortune.", [])
    w, reply = answer(t)
    _, lines = t.resolve(game, w, reply, [], "assist")
    assert lines == [("A watch passes.", "dim"), AMISS] and "777" in t.last["refused"]


def test_a_failure_changes_nothing_and_says_so(game):
    t, _ = typed(None)
    t.start(game, "I do something.", [])
    before = game.world.time
    w, reply = answer(t)
    turn, lines = t.resolve(game, w, reply, [], "assist")
    assert turn is None and lines == [HESITATE] and game.world.time == before


def test_a_wait_past_its_time_is_over(game, monkeypatch):
    monkeypatch.setattr("ai.typed.GRACE", 0.0)
    slow = lambda job, prompt: time.sleep(1.0) or {"prose": "Late.", "proposals": []}  # noqa: E731
    t, _ = typed(slow)
    monkeypatch.setattr("ai.typed.timeout_for", lambda bridge: 0.05)
    t.start(game, "I wait.", [])
    assert answer(t, 2.0)[1] is None


def test_esc_lets_the_wait_go_and_a_late_answer_is_never_read(game):
    slow = lambda job, prompt: time.sleep(0.3) or {"prose": "Late.", "proposals": []}  # noqa: E731
    t, _ = typed(slow)
    t.start(game, "I wait.", [])
    assert t.cancel() is not None and t.waiting is None
    time.sleep(0.5)
    assert t.poll() is None


def test_a_line_said_in_a_conversation_is_answered_and_remembered(game):
    npc, me = someone(game), game.player.id
    game.perform(Action("talk", npc.id))
    t, fake = typed({"reply": f"{npc.name} laughs. \"The marsh road? Bandits, friend.\"",
                     "summary": "You asked after the marsh road; they warned of bandits.",
                     "proposals": [{"kind": "feeling", "who": npc.name, "feeling": "amused", "strength": 0.2},
                                   {"kind": "minor_npc", "occupation": "tea seller", "traits": ["kind"]}]})
    t.start(game, "What news of the marsh road?", [])
    assert fake.calls[0][0] == "dialogue" and f"TALKING TO: {npc.name}" in fake.calls[0][1]
    w, reply = answer(t)
    _, lines = t.resolve(game, w, reply, [], "assist")
    assert lines[0][1] == "prose" and t.last["rejected"][0][1] == "not while talking"
    talked = [m for m in game.world.memories(npc.id, about=me) if m.event.kind == "talked"]
    assert talked and talked[-1].event.data["summary"].startswith("You asked after the marsh road")
    assert t.talk[0] == npc.id and t.talk[1][0] == "You: What news of the marsh road?"
    assert game.focus == npc.id  # still talking


def test_the_schemas_ask_for_paragraphs_and_proposals():
    assert INTENT_SCHEMA["required"] == ["prose", "proposals"]
    assert DIALOGUE_SCHEMA["required"] == ["reply", "summary", "proposals"]


# --- review focus ---------------------------------------------------------------------------------------------

def test_an_action_that_travels_ends_the_turn_in_the_new_place(game):
    routes = game.perform(Action("routes")).choices
    road = next(c for c in routes if c.action.verb == "travel")
    t, _ = typed({"prose": "You set out along the road.", "proposals": [{"kind": "action", "choice": road.label}]})
    start = game.place.id
    t.start(game, "I take the road out of town.", routes)
    w, reply = answer(t)
    turn, lines = t.resolve(game, w, reply, routes, "assist")
    assert game.place.id != start and lines[0] == ("You set out along the road.", "prose") and turn.choices


def test_an_answer_naming_a_stranger_is_not_shown_and_its_summary_is_the_engines(game):
    npc, me = someone(game), game.player.id
    game.perform(Action("talk", npc.id))
    t, _ = typed({"reply": "\"Ask Lord Baek Hwasan,\" they say.", "summary": "They sent you to Lord Baek Hwasan.",
                  "proposals": []})
    t.start(game, "Who rules here?", [])
    w, reply = answer(t)
    _, lines = t.resolve(game, w, reply, [], "assist")
    assert lines == [AMISS] and "Baek Hwasan" in t.last["refused"]
    talked = [m for m in game.world.memories(npc.id, about=me) if m.event.kind == "talked"]
    assert talked[-1].event.data["summary"] == "They spoke with you."


def fine_average(fn, n=20, rounds=5) -> float:
    """Wall time per call, the best of a few rounds (Windows' CPU clock ticks every 15.6 ms)."""
    fn()
    gc.collect()
    best = float("inf")
    for _ in range(rounds):
        start = time.perf_counter()
        for _ in range(n):
            fn()
        best = min(best, (time.perf_counter() - start) / n)
    return best


def test_the_prompt_is_built_in_6_ms_and_the_proposals_weighed_in_5(game):
    """Spec 14.8 asks under 20 ms; the grammar read once a process (plan ruling 10) makes it about 2."""
    npc = someone(game)
    rest = Choice("Rest a while", Action("rest"))
    proposals = [{"kind": "pay", "to": npc.name, "amount": 1}, {"kind": "feeling", "who": npc.name,
                                                                 "feeling": "grateful"},
                 {"kind": "deed", "text": f"You helped {npc.name}.", "tone": "kind"}, {"kind": "time", "watches": 1}]
    scene = Scene(game.world, game.player.id, game.place.id, [rest], "speed")
    assert fine_average(lambda: intent_prompt(game, f"I ask {npc.name} about the bandits.", [rest], [])) < 0.006
    assert fine_average(lambda: accept(scene, proposals)) < 0.005


def test_a_view_of_the_world_reads_no_grammar(game):
    """Each MCP request and each prefetch makes a View, which makes a Game: the grammar is not read again."""
    assert fine_average(lambda: View(game.world)) < 0.002
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_typed.py`
Expected: a collection error, `ModuleNotFoundError: No module named 'ai.intent'`.

- [ ] **Step 3: Write the new modules**

`ai/intent.py`:
```python
"""The two jobs of typed text (phase 6 spec 14.3-14.4): a typed action, and a line said in a conversation.

Each prompt is built on the game's thread (the world's connection belongs to it) from the state pack (6a), the
prefetch (6b), the paragraphs just shown, and the typed line; the backend answers in a worker thread. The replies'
proposals are the vocabulary of `ai/validate.py`, checked there.
"""

from ai.bridge import Job
from ai.pack import build_pack
from ai.prefetch import build_prefetch
from ai.validate import FEELINGS, HURTS, MAX_DEED, MAX_SEVERITY, MAX_STRENGTH, MAX_WATCHES, PROPOSALS, REALMS
from world.body import BODY_PARTS
from world.gen.npc import OCCUPATIONS, TRAITS

MODEL = "claude-sonnet-5"  # the menu's "Typed actions and talk" model replaces it (6b's per-job models)
TIMEOUTS = {"Claude Code": 30.0, "OpenCode": 90.0}  # OpenCode's free tier took 13-60 s (spec 14.2)
DEFAULT_TIMEOUT = 30.0
MAX_CHOICES = 40
TALK_LINES = 8
MAX_SUMMARY = 200

INTENT_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["prose", "proposals"], "properties": {
    "prose": {"type": "string", "maxLength": 1500}, "proposals": PROPOSALS}}
DIALOGUE_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["reply", "summary", "proposals"],
                   "properties": {"reply": {"type": "string", "maxLength": 1500},
                                  "summary": {"type": "string", "maxLength": MAX_SUMMARY}, "proposals": PROPOSALS}}


def _one_of(values) -> str:
    return "|".join(values)


VOCABULARY = (
    "CHANGES you may propose (each an object with \"kind\" and its fields; at most 4):\n"
    "- action: choice (exactly one of the CHOICES below), when the typed action is one of them\n"
    "- pay: to (a person here, by name), amount (silver, a whole number, at most what you carry)\n"
    "- give: to (a person here), item (the exact name of something you own and neither wield nor wear)\n"
    f"- feeling: who (a person here), feeling ({_one_of(FEELINGS)}), strength (0.1 to {MAX_STRENGTH})\n"
    f"- deed: text (what you did, at most {MAX_DEED} characters, naming only people you know), "
    "tone (kind|cruel|neutral|bold): a tale that may spread, weighed by heaven and your heart; one a line\n"
    "- tell: who (a person here), handle (the [handle] of a belief they hold, from the prompt): you learn it\n"
    f"- minor_npc: occupation ({_one_of(OCCUPATIONS)}), traits (1-2 of {_one_of(TRAITS)}), "
    f"realm ({_one_of(REALMS)}): someone new in the town\n"
    f"- hurt: location ({_one_of(BODY_PARTS)}), injury ({_one_of(HURTS)}), severity (1 to {MAX_SEVERITY}): you only\n"
    f"- time: watches (1 to {MAX_WATCHES}; four watches are a day)\n"
)
RULES = (
    "Propose only what the typed action itself causes; most actions cause one change or none. Name only people the "
    "prompt names; state no number the prompt does not carry or you do not propose, written as digits. Stay "
    "realistic for the player's state: their realm, their silver, what they own, where they are, what they know. "
    "Use a tool only for what the prompt lacks."
)
INTENT_SYSTEM = (
    "You are the game master of DeepMurim, a wuxia text game. The player types what their character does; you "
    "decide what happens. Write one paragraph of about 3-6 sentences of vivid second-person prose in the register "
    "of a wuxia novel, then propose the changes to the world it causes. If the typed action is one of the CHOICES, "
    "propose that choice as an action and tell only its beginning: the engine tells the rest. " + RULES + "\n\n"
    + VOCABULARY + "\nReply with JSON: {\"prose\": \"...\", \"proposals\": [...]}."
)
DIALOGUE_SYSTEM = (
    "You voice a person of DeepMurim, a wuxia text game: the one under TALKING TO. The player speaks to them; "
    "answer as they would, from what they are, what they remember and what they hold, and from nothing else. Write "
    "one paragraph of about 2-5 sentences: their words, and what they do as they say them, in the third person. "
    "Then sum up the exchange in one line, as they would remember it (at most 200 characters), and propose only "
    "what the words themselves cause (most talk causes none, or a feeling; passing on a belief they hold is a "
    "tell). There is no action and no newcomer in a conversation. " + RULES + "\n\n" + VOCABULARY
    + "\nReply with JSON: {\"reply\": \"...\", \"summary\": \"...\", \"proposals\": [...]}."
)


def timeout_for(bridge) -> float:
    return TIMEOUTS.get(getattr(bridge, "name", ""), DEFAULT_TIMEOUT)


def intent_job(timeout: float = DEFAULT_TIMEOUT) -> Job:
    return Job("intent", MODEL, timeout, INTENT_SCHEMA, INTENT_SYSTEM, tools=True)


def dialogue_job(timeout: float = DEFAULT_TIMEOUT) -> Job:
    return Job("dialogue", MODEL, timeout, DIALOGUE_SCHEMA, DIALOGUE_SYSTEM, tools=True)


def _told(recent: list[str]) -> str:
    return "\n".join(f"- {line}" for line in recent[-3:]) or "- (the story begins)"


def intent_prompt(game, typed: str, choices: list, recent: list[str]) -> str:
    labels = list(dict.fromkeys(c.label for c in choices))[:MAX_CHOICES]
    shown = "\n".join(f"- {label}" for label in labels) or "- (none)"
    return (f"STATE:\n{build_pack(game)}\n\n{build_prefetch(game, typed)}\n\nTOLD JUST BEFORE:\n{_told(recent)}\n\n"
            f"CHOICES (an action names one exactly):\n{shown}\n\nTHE PLAYER TYPES: {typed}")


def dialogue_prompt(game, typed: str, person: int, talk: list[str], recent: list[str]) -> str:
    name = game.world.entity(person).name
    said = "\n".join(f"- {line}" for line in talk[-TALK_LINES:]) or "- (they have just begun to talk)"
    return (f"STATE:\n{build_pack(game)}\n\n{build_prefetch(game, typed, focus=person)}\n\nTALKING TO: {name}\n\n"
            f"THIS CONVERSATION SO FAR:\n{said}\n\nTOLD JUST BEFORE:\n{_told(recent)}\n\nTHE PLAYER SAYS: {typed}")
```

`ai/typed.py`:
```python
"""A typed line the engine did not know, asked of the model and waited for (phase 6 spec 14.1-14.6).

`start` builds the prompt on the game's thread and asks in a daemon thread; `poll` (every frame) hands back the
answer once it has come or the wait is over; `cancel` lets it go (Esc). `resolve` checks the proposals, commits what
stands, and says what to show: the model's paragraph, and in assist mode the engine's line for each change. Any
failure changes nothing and says so.
"""

import hashlib
import threading
import time
from concurrent.futures import Future
from dataclasses import dataclass

from ai import deeds as D
from ai.guard import refusal
from ai.intent import TALK_LINES, dialogue_job, dialogue_prompt, intent_job, intent_prompt, timeout_for
from ai.narrate import RECENT, unwrap
from ai.validate import DIALOGUE_KINDS, KINDS, Scene, accept

GRACE = 5.0  # past the job's own timeout, the wait is over even if the worker never answers
HESITATE = ("You hesitate; nothing comes of it.", "dim")
AMISS = ("You try, but it does not go as you meant.", "dim")


@dataclass
class Waiting:
    typed: str
    job: object
    future: Future
    began: float
    talk_to: int | None  # the person spoken to (a conversation), or None (a typed action)
    prompt: str
    who: str             # the backend's name, for the waiting line


class Typed:
    def __init__(self, narration, clock=time.monotonic) -> None:
        self.narration = narration  # its backend, mode and recent paragraphs are shared
        self.clock = clock
        self.waiting: Waiting | None = None
        self.talk: tuple[int | None, list[str]] = (None, [])  # the conversation so far, with whom
        self.last: dict = {}  # the last exchange, as the overlay and the session log keep it

    def ready(self) -> bool:
        """Whether a typed line may be asked of the model now (the AI on, its backend able)."""
        n = self.narration
        if n.mode == "off" or n.unavailable() is not None:
            return False
        paused = getattr(n.bridge, "paused", None)
        return not (callable(paused) and paused())

    def start(self, game, typed: str, choices: list) -> None:
        bridge = self.narration.bridge
        timeout, recent = timeout_for(bridge), self.narration.recent
        if game.focus is not None:
            job, prompt = dialogue_job(timeout), dialogue_prompt(game, typed, game.focus, self._talk(game.focus),
                                                                   recent)
        else:
            job, prompt = intent_job(timeout), intent_prompt(game, typed, choices, recent)
        future: Future = Future()

        def work() -> None:
            if not future.set_running_or_notify_cancel():
                return
            try:
                future.set_result(bridge.call(job, prompt))
            except BaseException as exc:  # handed to `poll`: the world stays as it was
                future.set_exception(exc)
        threading.Thread(target=work, name="typed", daemon=True).start()
        self.waiting = Waiting(typed, job, future, self.clock(), game.focus, prompt,
                               getattr(bridge, "name", None) or "Claude")

    def poll(self):
        """(waiting, reply) once the answer has come or the wait is over (reply None: it failed); else None."""
        w = self.waiting
        if w is None:
            return None
        if w.future.done():
            try:
                reply = w.future.result()
            except Exception:
                reply = None
        elif self.clock() - w.began > w.job.timeout + GRACE:
            reply = None
        else:
            return None
        self.waiting = None
        return w, reply

    def cancel(self) -> Waiting | None:
        """Esc: the wait is let go; an answer that comes after is never read."""
        w, self.waiting = self.waiting, None
        if w is not None:
            w.future.cancel()
        return w

    def _talk(self, person: int) -> list[str]:
        with_whom, lines = self.talk
        return lines if with_whom == person else []

    def resolve(self, game, w: Waiting, reply, choices: list, mode: str):
        """(the turn or None, the lines to show). Accepted changes are committed even when the paragraph is not
        shown: they are what really happened."""
        record = {"job": w.job.name, "typed": w.typed, "prompt": w.prompt, "reply": reply, "accepted": [],
                  "rejected": [], "refused": None, "seconds": round(self.clock() - w.began, 2)}
        self.last = record
        if not isinstance(reply, dict):
            record["refused"] = "no reply"
            return None, [HESITATE]
        world, me, here = game.world, game.player.id, game.place.id
        dialogue = w.talk_to is not None
        salt = f"{world.time}:{hashlib.sha1(w.typed.encode()).hexdigest()[:8]}"
        done = accept(Scene(world, me, here, list(choices), salt), reply.get("proposals"),
                      DIALOGUE_KINDS if dialogue else KINDS)
        events = list(done.events)
        prose = unwrap(str(reply.get("reply" if dialogue else "prose") or ""))
        if dialogue:
            summary = " ".join(str(reply.get("summary") or "").split())
            if not summary or refusal(world, summary, me, here, w.prompt) is not None:
                summary = "They spoke with you."
            events.append(D.talked(me, w.talk_to, here, summary, w.typed))
        turn = game.apply_proposals(events, done.action)
        given = w.prompt + "\n" + "\n".join(text for text, _ in turn.lines)
        why = refusal(world, prose, me, here, given) if prose else "no prose"
        record.update(accepted=[e.data.get("proposal", {"kind": e.kind}) for e in events],
                      rejected=[[p, reason] for p, reason in done.rejected], refused=why)
        if why is not None:
            return turn, list(turn.lines) + [AMISS]
        self.narration.recent = (self.narration.recent + [prose])[-RECENT:]
        if dialogue:
            name = world.entity(w.talk_to).name
            _, lines = self.talk if self.talk[0] == w.talk_to else (None, [])
            self.talk = (w.talk_to, (lines + [f"You: {w.typed}", f"{name}: {prose}"])[-TALK_LINES:])
        return turn, [(prose, "prose")] + ([] if mode == "ai_only" else list(turn.lines))
```

`engine/ai_turns.py`:
```python
"""A typed line's accepted changes made into a turn (phase 6 spec 14.5-14.6).

The model's proposals are checked by `ai/validate.py`; what stands comes here as ordinary events, and at most one
engine action (a choice of this turn, run as if chosen). The turn's lines are the engine's own short record of each
change (each event's outcome lines, never the grammar's), then the action's own lines.
"""

from engine.actions import Turn


class AiTurnsMixin:
    def apply_proposals(self, events: list, action=None) -> Turn:
        self.last_briefs, self._narrated = [], []
        lines = []
        if events:
            self._commit(events)
            lines = [(text, "dim") for brief in self.last_briefs for text in brief.outcome]
        briefs = list(self.last_briefs)
        if action is not None:
            turn = self.perform(action)
            turn.lines[:0] = lines
            turn.narrated = [i + len(lines) for i in turn.narrated]
            self.last_briefs = briefs + self.last_briefs
            return turn
        turn = self._after_turn(self._turn(lines))
        turn.narrated = []  # the model's paragraph is this turn's prose; nothing is narrated again
        return turn
```

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/6c_task2.py`:
```python
"""Task 2's edits to existing files. Each edit replaces one exact anchor and stops if it is not found once."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"{path}: the anchor is found {text.count(old)} times: {old[:60]!r}"
    p.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")

edit('engine/game.py', r'''from engine.crisis import CrisisMixin
from engine.alchemy import AlchemyMixin
''', r'''from engine.crisis import CrisisMixin
from engine.ai_turns import AiTurnsMixin
from engine.alchemy import AlchemyMixin
''')

edit('engine/game.py', r'''class Game(KarmaMixin, TribulationMixin, HeartMixin, CraftsMixin, AlchemyWorldMixin, AlchemyMixin, GearMixin, IntrigueMixin, CrisisMixin, SealedMixin, RivalMixin, ChamberMixin, DelveMixin, LineageMixin, MarketMixin, SkyMixin, TournamentMixin, WorldMixin, FactionsMixin, JoiningMixin, RanksMixin, DutiesMixin, PoliticsMixin, LeavingMixin, LawMixin, LandMixin, FoundingMixin, SectMixin, SeasonsMixin, GossipMixin, MasksMixin, InventingMixin, DealingsMixin, RoadsMixin, FightMixin, GameHooks):
''', r'''class Game(AiTurnsMixin, KarmaMixin, TribulationMixin, HeartMixin, CraftsMixin, AlchemyWorldMixin, AlchemyMixin, GearMixin, IntrigueMixin, CrisisMixin, SealedMixin, RivalMixin, ChamberMixin, DelveMixin, LineageMixin, MarketMixin, SkyMixin, TournamentMixin, WorldMixin, FactionsMixin, JoiningMixin, RanksMixin, DutiesMixin, PoliticsMixin, LeavingMixin, LawMixin, LandMixin, FoundingMixin, SectMixin, SeasonsMixin, GossipMixin, MasksMixin, InventingMixin, DealingsMixin, RoadsMixin, FightMixin, GameHooks):
''')

edit('narrate/procedural.py', r'''
class Grammar:
''', r'''
_LOADED: dict[str, dict] = {}  # directory -> its tables (Grammar.load)


class Grammar:
''')

edit('narrate/procedural.py', r'''        directory = directory or bundled("narrate", "grammar")
        tables: dict = {}
        for path in sorted(directory.glob("*.toml")):
            with open(path, "rb") as handle:
                for key, value in tomllib.load(handle).items():
                    if key == "symbols":
                        tables.setdefault("symbols", {}).update(value)
                    else:
                        tables[key] = value
        return cls(tables)
''', r'''        """The grammar of a directory, read once a process: it never changes while the game runs, and every Game
        (each MCP request's View makes one, phase 6c) would otherwise parse all of it again (12 ms)."""
        directory = Path(directory or bundled("narrate", "grammar"))
        key = str(directory.resolve())
        if key not in _LOADED:
            tables: dict = {}
            for path in sorted(directory.glob("*.toml")):
                with open(path, "rb") as handle:
                    for name, value in tomllib.load(handle).items():
                        if name == "symbols":
                            tables.setdefault("symbols", {}).update(value)
                        else:
                            tables[name] = value
            _LOADED[key] = tables
        return cls(_LOADED[key])
''')

print("task 2 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/6c_task2.py`
Expected: `task 2 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_typed.py tests/test_ai_proposals.py`
Expected: `30 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow and live ones are deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: typed actions and talk - two jobs, asked and waited for, resolved into a turn; the grammar read once

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 3: The App: the router, the animated wait, Esc, what is shown

- A typed line the parser does not know goes to the model (never a number), when the AI is on and its backend can answer:
  - in a conversation, as a line said to that person;
  - else, as a typed action.
- While it waits, input pauses under a line drawn from the clock: `· • o O o •`, eight frames a second (ruling 1).
- Esc lets it go, and the typed line is marked "(let go)" (ruling 2).
- The answer is shown through `_show(turn, shown)`, never narrated again.
- A backend that logged out meanwhile is said, and the AI turned off (review focus 2).

**Files:**
- Create: `tests/test_ai_typed_app.py`
- Modify (by `.patches/6c_task3.py`): `app.py`

**Interfaces:**
- Consumes: Task 2's `Typed`, `HESITATE`; `App.submit`, `App.poll`, `App._show`, `App.grid`, `App._close_game`.
- Produces:
  - `app`: `WAIT_FRAMES`, `WAIT_FPS`; `App.typed`, `App._ask_ai(text) -> bool`, `App._let_go()`, `App._typed_done(waiting, reply)`, `App.waiting_line(now=None) -> str`, `App._show(turn, shown=None)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_ai_typed_app.py`:
```python
import time

import pytest

import systems.encounters as encounters
from ai.fake import FakeClaude
from app import App, WAIT_FRAMES
from config import Config
from engine.actions import Action
from systems.creation import CreationChoice
from world.gen.materialize import people_at


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def make_app(tmp_path, mode, *replies):
    """The typed lines' replies, in order; every prose call fails (the engine's words stand), so it takes none."""
    script = list(replies)

    def by_job(job, prompt):
        if job.name == "narrate" or not script:
            return None
        reply = script.pop(0)
        return reply(job, prompt) if callable(reply) else reply
    fake = FakeClaude(*[by_job] * 50)
    app = App(Config(ai_mode=mode), tmp_path / "saves", tmp_path / "settings.json", logs_dir=tmp_path / "logs",
              bridge=fake)
    app.start_new("Mo Rin", world_seed=11, creation=CreationChoice("origin", "hunter"))
    app.state = "game"
    return app, fake


def asked(fake):
    """The calls of typed lines (prose calls aside)."""
    return [job for job, _ in fake.calls if job != "narrate"]


def type_line(app, text):
    app.command = text
    app.handle_key("return", "\r")


def settle(app, wait=5.0):
    deadline = time.monotonic() + wait
    while app.typed.waiting is not None and time.monotonic() < deadline:
        app.poll()
        time.sleep(0.01)
    assert app.typed.waiting is None


def screen(app):
    return "\n".join("".join(cell[0] if cell else " " for cell in row) for row in app.grid(120, 40))


def someone(app):
    return people_at(app.game.world, app.game.place.id, exclude=app.game.player.id)[0]


def test_with_the_ai_off_a_line_the_engine_does_not_know_is_unknown_as_ever(tmp_path):
    app, fake = make_app(tmp_path, "off", {"prose": "x", "proposals": []})
    type_line(app, "I juggle three oranges.")
    assert asked(fake) == [] and app.typed.waiting is None
    app.shutdown()


def test_a_command_or_a_number_never_goes_to_the_model(tmp_path):
    app, fake = make_app(tmp_path, "assist")
    type_line(app, "look")
    type_line(app, "99")
    assert asked(fake) == []
    app.shutdown()


def test_a_typed_action_waits_with_a_moving_line_then_shows_its_paragraph(tmp_path):
    slow = lambda job, prompt: time.sleep(0.2) or {"prose": "You juggle; a child laughs.",  # noqa: E731
                                                   "proposals": [{"kind": "time", "watches": 1}]}
    app, fake = make_app(tmp_path, "assist", slow)
    type_line(app, "I juggle three oranges.")
    assert app.typed.waiting is not None and app.log[-1] == ("> I juggle three oranges.", "player")
    assert "considers it" in screen(app)
    assert app.waiting_line(0.0) != app.waiting_line(1.0 / 8)  # it moves, about eight frames a second
    assert {app.waiting_line(i / 8)[0] for i in range(len(WAIT_FRAMES))} == set(WAIT_FRAMES)
    app.handle_key("x", "x")  # input waits
    assert app.command == ""
    settle(app)
    texts = [t for t, _ in app.log]
    assert "You juggle; a child laughs." in texts and "A watch passes." in texts
    assert "considers it" not in screen(app)
    app.shutdown()


def test_in_ai_only_the_paragraph_alone_is_shown(tmp_path):
    app, _ = make_app(tmp_path, "ai_only", {"prose": "You wait by the well.", "proposals": [{"kind": "time",
                                                                                            "watches": 1}]})
    type_line(app, "I wait by the well.")
    settle(app)
    assert app.log[-1] == ("You wait by the well.", "prose") and "A watch passes." not in [t for t, _ in app.log]
    app.shutdown()


def test_esc_lets_the_wait_go_and_nothing_happens(tmp_path):
    slow = lambda job, prompt: time.sleep(0.3) or {"prose": "Late.", "proposals": [{"kind": "time",  # noqa: E731
                                                                                     "watches": 3}]}
    app, _ = make_app(tmp_path, "assist", slow)
    before = app.game.world.time
    type_line(app, "I wait a long while.")
    app.handle_key("escape", "\x1b")
    assert app.typed.waiting is None and app.state == "game"
    assert app.log[-1] == ("> I wait a long while. (let go)", "dim")
    time.sleep(0.5)
    app.poll()
    assert app.game.world.time == before and "Late." not in [t for t, _ in app.log]
    app.shutdown()


def test_a_failure_says_you_hesitate(tmp_path):
    app, _ = make_app(tmp_path, "assist", None)
    type_line(app, "I do a thing.")
    settle(app)
    assert app.log[-1] == ("You hesitate; nothing comes of it.", "dim")
    app.shutdown()


def test_in_a_conversation_a_typed_line_is_said_to_them(tmp_path):
    app, fake = make_app(tmp_path, "assist")
    npc = someone(app)
    app._show(app.game.perform(Action("talk", npc.id)))
    replies = {"reply": f"{npc.name} nods slowly.", "summary": "You greeted them.", "proposals": []}
    fake.script.clear()
    fake.add(*[lambda job, prompt: replies if job.name == "dialogue" else None] * 5)
    type_line(app, "Fine weather for the season.")
    settle(app)
    assert asked(fake)[-1] == "dialogue" and app.log[-1] == (f"{npc.name} nods slowly.", "prose")
    assert app.game.focus == npc.id and app.choices  # still talking; the choices stay
    app.shutdown()


def test_a_backend_that_cannot_answer_leaves_the_line_unknown(tmp_path):
    app, fake = make_app(tmp_path, "assist")
    fake._available = False
    type_line(app, "I juggle.")
    assert asked(fake) == [] and app.typed.waiting is None
    app.shutdown()


# --- review focus ---------------------------------------------------------------------------------------------

def test_quitting_while_a_typed_line_waits_closes_at_once_and_applies_nothing(tmp_path):
    slow = lambda job, prompt: time.sleep(0.5) or {"prose": "Late.", "proposals": [{"kind": "time",  # noqa: E731
                                                                                     "watches": 2}]}
    app, _ = make_app(tmp_path, "assist", slow)
    save, before = app.save_path, app.game.world.time
    type_line(app, "I wait a long while.")
    began = time.perf_counter()
    app.shutdown()
    assert time.perf_counter() - began < 1.0 and app.typed.waiting is None
    time.sleep(0.7)
    from engine.game import Game
    game = Game.load(save)
    assert game.world.time == before
    game.close()


def test_logged_out_during_a_wait_the_line_hesitates_and_the_ai_says_why_and_turns_off(tmp_path):
    app, fake = make_app(tmp_path, "assist")

    def logged_out(job, prompt):
        fake._available = False
        return None
    fake.script.clear()
    fake.add(logged_out)
    type_line(app, "I juggle.")
    settle(app)
    texts = [t for t, _ in app.log]
    assert "You hesitate; nothing comes of it." in texts and any("cannot be used" in t for t in texts)
    assert app.config.ai_mode == "off" and app.narration.mode == "off" and app.mcp is None
    app.shutdown()
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_typed_app.py`
Expected: a collection error, `ImportError: cannot import name 'WAIT_FRAMES' from 'app'`.

- [ ] **Step 3: Write the new modules**

None in this task: its code is all edits (Step 4).

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/6c_task3.py`:
```python
"""Task 3's edits to existing files. Each edit replaces one exact anchor and stops if it is not found once."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"{path}: the anchor is found {text.count(old)} times: {old[:60]!r}"
    p.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")

edit('app.py', r'''from ai.narrate import MODE_WORDS, Narration
from config import PALETTE, Config
''', r'''from ai.narrate import MODE_WORDS, Narration
from ai.typed import HESITATE, Typed
from config import PALETTE, Config
''')

edit('app.py', r'''MAX_VIOLATIONS = 200
INSTANT_KEYS = "123456789"  # submit on press, so a held key must not auto-repeat them
''', r'''MAX_VIOLATIONS = 200
WAIT_FRAMES = ("·", "•", "o", "O", "o", "•")  # the font has no ∘ ○ ◎ (plan ruling)
WAIT_FPS = 8
INSTANT_KEYS = "123456789"  # submit on press, so a held key must not auto-repeat them
''')

edit('app.py', r'''        self.narration = Narration(bridge, config.ai_mode, factory=self._backend)  # phase 6: the model's prose
        self._given_bridge = bridge  # one handed in (the tests' FakeClaude) is the backend, built anew or not
''', r'''        self.narration = Narration(bridge, config.ai_mode, factory=self._backend)  # phase 6: the model's prose
        self.typed = Typed(self.narration)  # phase 6c: a typed line the engine did not know, asked of the model
        self._typed_at: int | None = None  # where that line stands in the log
        self._given_bridge = bridge  # one handed in (the tests' FakeClaude) is the backend, built anew or not
''')

edit('app.py', r'''    def _game_key(self, key: str, text: str) -> None:
        if self.ai_menu is not None:
''', r'''    def _game_key(self, key: str, text: str) -> None:
        if self.typed.waiting is not None:  # the turn waits for the model's answer (spec 14.2)
            if key == "escape":
                self._let_go()
            elif key == "f12":
                self.debug_visible = not self.debug_visible
            return
        if self.ai_menu is not None:
''')

edit('app.py', r'''            return
        self.log.append((f"> {text.strip()}", "player"))
''', r'''            return
        if action.verb == "unknown" and self._ask_ai(text):
            return
        self.log.append((f"> {text.strip()}", "player"))
''')

edit('app.py', r'''        self._follow_exit()

''', r'''        self._follow_exit()

    def _ask_ai(self, text: str) -> bool:
        """A typed line the engine does not know goes to the model, when it may (spec 14.1)."""
        typed = " ".join(text.split())[:200]
        player = self.game.player
        if not typed or typed.isdigit() or player.data.get("dying") or player.data.get("dead")                 or not self.typed.ready():
            return False
        self.narration.settle(self.log)
        if self.log:
            self.log.append(("", "default"))
        self.log.append((f"> {typed}", "player"))
        self._typed_at = len(self.log) - 1
        self._record("command", text=text, verb="ai")
        try:
            self.typed.start(self.game, typed, self.choices + self.extra)
        except Exception as exc:  # the model's layer never breaks a turn
            self._record("ai_error", error=repr(exc))
            self.log.append(HESITATE)
        return True

    def _let_go(self) -> None:
        """Esc while waiting: nothing happens, and the typed line says so."""
        waiting = self.typed.cancel()
        at = self._typed_at
        if waiting is not None and at is not None and at < len(self.log) and self.log[at] == (f"> {waiting.typed}", "player"):
            self.log[at] = (f"> {waiting.typed} (let go)", "dim")
        self._record("ai", job=waiting.job.name if waiting else "", typed=waiting.typed if waiting else "",
                     cancelled=True)

    def _typed_done(self, waiting, reply) -> None:
        try:
            turn, lines = self.typed.resolve(self.game, waiting, reply, self.choices + self.extra,
                                             self.narration.mode)
        except Exception as exc:  # what was accepted is in the save; the screen falls back to the engine's word
            self.record_crash(exc, "typed line")
            turn, lines = None, [HESITATE]
        self._record("ai", **{k: v for k, v in self.typed.last.items() if k != "prompt"})
        if turn is None:
            self.log.extend(lines)
            why = self.narration.unavailable()
            if why is not None and self.narration.mode != "off":  # logged out meanwhile: said, and turned off
                self.narration.mode = self.config.ai_mode = "off"
                self.log.append((f"{self.narration.who}'s prose cannot be used: {why}.", "system"))
                self._save_settings()
                self._ai_server()
            return
        self._show(turn, lines)
        self._follow_exit()

    def waiting_line(self, now: float | None = None) -> str:
        """The animated line under a typed line while the model is asked (spec 14.2): drawn from the clock."""
        now = time.monotonic() if now is None else now
        frame = WAIT_FRAMES[int(now * WAIT_FPS) % len(WAIT_FRAMES)]
        who = self.typed.waiting.who if self.typed.waiting else ""
        return f"{frame} {who} considers it...  (Esc lets it go)"

''')

edit('app.py', r'''        """Every frame: Claude's prose for the last turn, if it has come (phase 6)."""
''', r'''        """Every frame: the answer to a typed line (6c), and the prose for the last turn (phase 6), if come."""
        if self.typed.waiting is not None and self.game is not None:
            got = self.typed.poll()
            if got is not None:
                self._typed_done(*got)
''')

edit('app.py', r'''    def _show(self, turn: Turn) -> None:
''', r'''    def _show(self, turn: Turn, shown: list | None = None) -> None:
        """Put a turn on screen: its own lines, or (a typed line's turn, 6c) the lines it was resolved into, which
        are never narrated again."""
''')

edit('app.py', r'''        self.narration.settle(self.log)  # a turn left before its prose came keeps its own text
        if self.log:
            self.log.append(("", "default"))
''', r'''        self.narration.settle(self.log)  # a turn left before its prose came keeps its own text
        if shown is None and self.log:
            self.log.append(("", "default"))
''')

edit('app.py', r'''        self.log.extend(turn.lines)
''', r'''        self.log.extend(turn.lines if shown is None else shown)
''')

edit('app.py', r'''        del self.log[:-MAX_LOG]
        if self.game is not None:
            try:
''', r'''        del self.log[:-MAX_LOG]
        if self.game is not None and shown is None:
            try:
''')

edit('app.py', r'''    def _close_game(self) -> None:
        self.narration.reset()
''', r'''    def _close_game(self) -> None:
        self.typed.cancel()
        self.narration.reset()
''')

edit('app.py', r'''        choices = [c.label for c in self.choices]
        if self.ai_menu is not None:
''', r'''        choices = [c.label for c in self.choices]
        if self.typed.waiting is not None and not self.debug_visible:
            log, command = log + [(self.waiting_line(), "dim")], ""
        if self.ai_menu is not None:
''')

print("task 3 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/6c_task3.py`
Expected: `task 3 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_typed_app.py tests/test_app.py tests/test_ai_narration.py tests/test_ai_menu.py`
Expected: `33 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow and live ones are deselected).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: type what you do - the model asked, an animated wait, Esc lets it go, the paragraph shown

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 4: The overlay, bug reports, help, the fork guide, fuzz and live round trips

- F12 shows the last typed line: its job and time, what stood, each rejection's reason, and why a paragraph was refused.
- The session log (and so every bug report) keeps the whole exchange: the prompt, the raw reply, and the verdicts.
- Help says how to type; the fork guide's section 18 tells how to add a proposal kind.
- Fuzz tests throw random proposals and replies, valid and not, at the validator and the App.
- Live tests (marked `live`, `DEEPMURIM_LIVE=1`) make one typed action and one line of talk on Claude Code and on OpenCode.

**Files:**
- Create: `tests/test_ai_typed_debug.py`
- Modify (by `.patches/6c_task4.py`): `app.py`, `docs/world-events.md`, `engine/game.py`, `tests/test_ai_live.py`

**Interfaces:**
- Consumes: Everything above.
- Produces:
  - `App._claude_lines` (the typed line's verdicts); `docs/world-events.md` section 18; `tests/test_ai_live.py`'s `a_game`, `typed_round_trips` and two live tests.

- [ ] **Step 1: Write the failing tests**

`tests/test_ai_typed_debug.py`:
```python
import json
import random
import time
from pathlib import Path

import pytest

import systems.encounters as encounters
from ai.fake import FakeClaude
from ai.validate import KINDS, Scene, accept
from app import App
from config import Config
from debug.invariants import check_world
from engine.game import Game
from systems.creation import CreationChoice
from world.gen.materialize import people_at


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def make_app(tmp_path, *replies, mode="assist"):
    script = list(replies)

    def by_job(job, prompt):  # prose calls fail (the engine's words stand); typed lines take the script
        return None if job.name == "narrate" or not script else script.pop(0)
    app = App(Config(ai_mode=mode), tmp_path / "saves", tmp_path / "settings.json", logs_dir=tmp_path / "logs",
              bridge=FakeClaude(*[by_job] * 50))
    app.start_new("Mo Rin", world_seed=11, creation=CreationChoice("origin", "hunter"))
    app.state = "game"
    return app


def type_and_wait(app, text):
    app.command = text
    app.handle_key("return", "\r")
    for _ in range(500):
        if app.typed.waiting is None:
            return
        app.poll()
        time.sleep(0.01)
    raise AssertionError("no answer came")


def test_the_overlay_tells_the_last_typed_line_and_each_verdict(tmp_path):
    app = make_app(tmp_path, {"prose": "You wait, and spend 900 silver.", "proposals": [
        {"kind": "time", "watches": 1}, {"kind": "pay", "to": "Nobody", "amount": 900}]})
    type_and_wait(app, "I wait a watch.")
    text = "\n".join(t for t, _ in app.debug_lines())
    assert "typed (intent" in text and "I wait a watch." in text and "accepted: time" in text
    assert "rejected pay: they are not here" in text and "paragraph refused: it states 900" in text
    app.shutdown()


def test_the_session_log_keeps_the_typed_exchange_for_bug_reports(tmp_path):
    app = make_app(tmp_path, {"prose": "You wait.", "proposals": [{"kind": "time", "watches": 1}]})
    type_and_wait(app, "I wait a watch.")
    folder = app.bug_report()
    records = [json.loads(line) for line in (folder / "session.jsonl").read_text(encoding="utf-8").splitlines()]
    typed = [r for r in records if r.get("kind") == "ai" and r.get("job") == "intent"]
    assert typed and "THE PLAYER TYPES" in typed[-1]["prompt"] and typed[-1]["accepted"] == [{"kind": "time",
                                                                                               "watches": 1}]
    app.shutdown()


def test_help_tells_how_to_type_what_you_do(tmp_path):
    app = make_app(tmp_path, mode="off")
    app.submit("help")
    assert any("type what you do" in t for t, _ in app.log)
    app.shutdown()


def test_the_fork_guide_tells_how_to_add_a_proposal_kind():
    guide = (Path(__file__).parent.parent / "docs" / "world-events.md").read_text(encoding="utf-8")
    assert "## 18. Typed actions and free talk (phase 6c)" in guide and "**Adding a proposal kind:**" in guide


# --- fuzz (spec 14.9): random proposals, valid and not, never break the world --------------------------------

NAMES = ["Nobody Here", "", None, 7]
FIELDS = {"amount": [1, 2, 0, -5, 10 ** 9, "ten", True], "watches": [1, 3, 0, 9, 2.5], "strength": [0.1, 0.5, 0.9, -1],
          "severity": [1, 2, 3, 0], "feeling": ["grateful", "fear", "glee"], "tone": ["kind", "cruel", "sly"],
          "location": ["head", "left arm", "tail"], "injury": ["cut", "bruise", "hex"],
          "occupation": ["tea seller", "monk", "astronaut"], "traits": [["kind"], ["kind", "proud"], ["evil"], []],
          "realm": ["mortal", "third-rate", "immortal"], "handle": ["b0000000000", "nonsense"],
          "text": ["You helped carry water.", "You bested Mo Tianlong.", "x" * 300], "item": ["a sword", ""],
          "choice": ["Rest a while", "Fly"]}


def random_proposal(rng, here):
    p = {"kind": rng.choice(list(KINDS) + ["fly", None])}
    for key in rng.sample(sorted(FIELDS), rng.randint(0, 6)):
        p[key] = rng.choice(FIELDS[key])
    for key in ("to", "who"):
        if rng.random() < 0.7:
            p[key] = rng.choice(here + NAMES)
    return p


def test_random_proposals_never_break_a_rule_or_the_game(tmp_path):
    rng = random.Random(6)
    game = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    game.start()
    try:
        for round_ in range(120):
            here = [p.name for p in people_at(game.world, game.place.id, exclude=game.player.id)][:6]
            proposals = [random_proposal(rng, here) for _ in range(rng.randint(0, 7))]
            if rng.random() < 0.1:
                proposals = rng.choice([None, "nonsense", [1, "two"], {"kind": "time"}])
            done = accept(Scene(game.world, game.player.id, game.place.id, [], f"fuzz{round_}"), proposals)
            game.apply_proposals(done.events, None)
            if round_ % 30 == 29:
                assert check_world(game.world) == []
        assert check_world(game.world) == []
    finally:
        game.close()


def test_random_replies_through_the_app_never_break_it(tmp_path):
    rng = random.Random(7)
    replies = []
    for _ in range(12):
        replies.append(rng.choice([None, "nonsense", {"prose": 5}, {"proposals": []},
                                   {"prose": "You stand a while.", "proposals": [
                                       random_proposal(rng, []) for _ in range(rng.randint(0, 5))]}]))
    app = make_app(tmp_path, *replies)
    for i in range(12):
        type_and_wait(app, f"I try something odd, number {chr(97 + i)}.")
        assert app.state == "game" and app.crash_count == 0
    assert app.violations == []
    app.shutdown()
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_typed_debug.py`
Expected: `4 failed, 2 passed`: the overlay, the session log (`KeyError: 'prompt'`), help and the guide fail; the two fuzz tests pass (ruling 8).

- [ ] **Step 3: Write the new modules**

None in this task: its code is all edits (Step 4).

- [ ] **Step 4: Apply the edits to existing files**

Each edit replaces one exact anchor and stops if the anchor is not found once.

`.patches/6c_task4.py`:
```python
"""Task 4's edits to existing files. Each edit replaces one exact anchor and stops if it is not found once."""
from pathlib import Path


def edit(path, old, new):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"{path}: the anchor is found {text.count(old)} times: {old[:60]!r}"
    p.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")

edit('app.py', r'''        self._record("ai", **{k: v for k, v in self.typed.last.items() if k != "prompt"})
''', r'''        self._record("ai", **self.typed.last)  # the prompt, the raw reply, each proposal's verdict (spec 8)
''')

edit('app.py', r'''            lines.append((f"  prose refused: {n.refused}", "red"))
        lines.append(("", "default"))
''', r'''            lines.append((f"  prose refused: {n.refused}", "red"))
        t = self.typed.last
        if t:  # the last typed line (6c): its job, what stood, what did not, and why the paragraph was not shown
            kinds = ", ".join(str(p.get("kind")) for p in t.get("accepted", [])) or "nothing"
            lines.append((f"  typed ({t['job']}, {t.get('seconds', 0.0):.1f} s): {t['typed'][:60]}", "default"))
            lines.append((f"    accepted: {kinds}", "default"))
            lines += [(f"    rejected {p.get('kind')}: {why}", "red") for p, why in t.get("rejected", [])]
            if t.get("refused"):
                lines.append((f"    paragraph refused: {t['refused']}", "red"))
        lines.append(("", "default"))
''')

edit('docs/world-events.md', r'''needs a tool.

''', r'''needs a tool.


## 18. Typed actions and free talk (phase 6c)

**The router** (`App.submit`): a typed line the command parser does not know (never a number) goes to the model
when the AI is on and its backend can answer: in a conversation (`game.focus`) as a line said to that person (the
`dialogue` job), else as a typed action (the `intent` job). `ai/intent.py` holds both jobs and their prompts (the
state pack, the prefetch, the last paragraphs, this turn's choices as words, the typed line).

**The wait** (`ai/typed.py`, `Typed`): the prompt is built on the game's thread and asked in a daemon thread;
`App.poll` hands the answer to `Typed.resolve` when it comes. Input waits meanwhile, under a line drawn from the
clock (`App.waiting_line`); Esc lets the wait go and nothing happens. A timeout or any failure says "You hesitate".

**Proposals** (`ai/validate.py`): `accept(scene, proposals, kinds)` returns the events that may stand, at most one
engine action (a choice of this turn), and the rest with their reasons. There is no retry. What stands is committed
by `Game.apply_proposals` (`engine/ai_turns.py`) as ordinary events marked `ai: true`; `check_ai` (in
`debug/invariants.py`) holds every such event to its kind's limits.

**Adding a proposal kind:**
1. In `ai/validate.py`: the kind in `KINDS` (and in `DIALOGUE_KINDS` if talk may cause it), its fields in
   `PROPOSAL`, and its checks in `check`, returning an event or a reason.
2. In `ai/deeds.py`: the event's builder (its data carries `ai: True` and the proposal), its kind in `KINDS`, and
   its `@effect`.
3. In `narrate/ai_text.py`: an `@outcome` giving its one engine line (shown under the paragraph in assist mode) and
   a `@summary` for the journal; in `narrate/grammar/ai.toml`, its table.
4. In `ai/intent.py`: a line in `VOCABULARY`, so the model knows it; in `check_ai`, its limits.
''')

edit('engine/game.py', r'''    ("  temple | alms | incense | fortune: karma, and heaven's patience", "system"),
    ("  F1 the AI | F2 swap art side | F3 hide art | F4 character sheet | F9 report a bug | F12 debug | Esc menu",
''', r'''    ("  temple | alms | incense | fortune: karma, and heaven's patience", "system"),
    ("  With the AI on (F1): type what you do; in a conversation, type what you say", "system"),
    ("  F1 the AI | F2 swap art side | F3 hide art | F4 character sheet | F9 report a bug | F12 debug | Esc menu",
''')

edit('tests/test_ai_live.py', r'''"""One real round trip through `claude -p` (phase 6 spec 11). Marked `live` and needs DEEPMURIM_LIVE=1."""
''', r'''"""Real round trips (phase 6 spec 11, 13.7, 14.9): prose, typed actions and talk. Marked `live`; needs DEEPMURIM_LIVE=1."""
''')

edit('tests/test_ai_live.py', r'''        reply = door.call(narrate_job(timeout=120.0), PROMPT)
    finally:
        door.close()
    assert reply is not None and 0 < len(reply["prose"]) <= 1500, list(door.exchanges)[-1].error
''', r'''        reply = door.call(narrate_job(timeout=120.0), PROMPT)
    finally:
        door.close()
    assert reply is not None and 0 < len(reply["prose"]) <= 1500, list(door.exchanges)[-1].error


def a_game(tmp_path, monkeypatch):
    import systems.encounters as encounters
    from engine.game import Game
    from systems.creation import CreationChoice
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
    game = Game.new(tmp_path / "live.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    game.start()
    return game


def typed_round_trips(door, game, timeout):
    """One typed action and one line of talk (6c): each answered in its shape, its proposals weighed."""
    from ai.intent import dialogue_job, dialogue_prompt, intent_job, intent_prompt
    from ai.validate import DIALOGUE_KINDS, Scene, accept
    from world.gen.materialize import people_at
    person = people_at(game.world, game.place.id, exclude=game.player.id)[0]
    scene = Scene(game.world, game.player.id, game.place.id, [], "live")
    acted = door.call(intent_job(timeout), intent_prompt(game, "I sit by the well and listen to the gossip.", [], []))
    assert acted is not None and acted["prose"], list(door.exchanges)[-1].error
    accept(scene, acted["proposals"])
    said = door.call(dialogue_job(timeout), dialogue_prompt(game, "What news of the roads?", person.id, [], []))
    assert said is not None and said["reply"] and said["summary"], list(door.exchanges)[-1].error
    accept(scene, said["proposals"], DIALOGUE_KINDS)


def test_claude_code_answers_a_typed_action_and_a_line_of_talk(tmp_path, monkeypatch):
    from ai.backends import ClaudeCode
    door = ClaudeCode()
    if not door.available()[0]:
        pytest.skip(door.available()[1])
    game = a_game(tmp_path, monkeypatch)
    try:
        typed_round_trips(door, game, 60.0)
    finally:
        door.close()
        game.close()


def test_opencode_answers_a_typed_action_and_a_line_of_talk(tmp_path, monkeypatch):
    from ai.backends import OpenCode, opencode_exe
    from ai.models import OpenCodeModels
    exe = opencode_exe()
    if exe is None:
        pytest.skip("OpenCode is not installed")
    free = OpenCodeModels(exe).free()
    if not free:
        pytest.skip("OpenCode offers no free model")
    door = OpenCode(models={"intent": free[0], "dialogue": free[0]}, workdir=Path("logs") / "live-opencode")
    game = a_game(tmp_path, monkeypatch)
    try:
        typed_round_trips(door, game, 150.0)
    finally:
        door.close()
        game.close()
''')

print("task 4 edits applied")
```

Run: `.venv/Scripts/python.exe .patches/6c_task4.py`
Expected: `task 4 edits applied`.

- [ ] **Step 5: Run the task's tests**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_ai_typed_debug.py tests/test_ai_debug.py tests/test_ai_live.py`
Expected: `11 passed, 5 deselected`.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: every test passes (the slow and live ones are deselected).

- [ ] **Step 7: Run the soak**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -m slow`
Expected: `2 passed`.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: a typed line's verdicts on F12 and in bug reports, help, the fork guide's section 18, fuzz and live round trips

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

## Self-review

- **Spec coverage (§14):**
  - 14.1 the router (Task 3);
  - 14.2 the wait (Tasks 2 and 3);
  - 14.3 typed actions and 14.4 free talk (Tasks 2 and 3);
  - 14.5 proposals, with no retry (Tasks 1 and 2);
  - 14.6 what is shown (Tasks 2 and 3);
  - 14.7 the debug rules (Tasks 1 and 4);
  - 14.8 speed (Task 2: the prompt, the validator and a `View` timed; Task 3: the AI off costs nothing);
  - 14.9 testing (every task; fuzz and live in Task 4).
- **Dry run:**
  - every task was applied in order to a copy of master; its tests failed as each Step 2 says, then passed;
  - the whole suite passed after every task, and the soak at the end;
  - the live round trips (a typed action and a line of talk) passed on Claude Code and on OpenCode.
