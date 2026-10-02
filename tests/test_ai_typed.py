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
