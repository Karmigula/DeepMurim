"""Phase 6c's final review: the fixes, each pinned by a test that failed first."""
import gc
import time

import pytest

import systems.encounters as encounters
from ai.fake import FakeClaude
from ai.guard import refusal
from ai.narrate import Narration
from ai.typed import AMISS, Typed
from ai.validate import Scene, accept
from app import App
from config import Config
from debug.invariants import check_ai
from engine.actions import Action, Choice
from engine.game import Game
from systems.creation import CreationChoice
from systems.purse import silver_of
from systems.time import advance
from world.events import commit
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


def scene(game, choices=(), salt="r"):
    return Scene(game.world, game.player.id, game.place.id, list(choices), salt)


def asked(game, reply, typed_line, choices=(), mode="assist"):
    t = Typed(Narration(FakeClaude(reply), mode))
    t.start(game, typed_line, list(choices))
    for _ in range(500):
        got = t.poll()
        if got is not None:
            return t, got
        time.sleep(0.01)
    raise AssertionError("no answer")


def test_a_paragraph_telling_a_rejected_payment_is_refused_though_the_player_typed_its_sum(game):
    npc, me = someone(game), game.player.id
    mine = silver_of(game.world, me)
    assert mine < 500
    t, (w, reply) = asked(game, {"prose": f"You press 500 silver into the hand of {npc.name}.",
                                 "proposals": [{"kind": "pay", "to": npc.name, "amount": 500}]},
                          f"I give {npc.name} 500 silver.")
    _, lines = t.resolve(game, w, reply, [], "assist")
    assert lines == [AMISS] and "500" in t.last["refused"] and silver_of(game.world, me) == mine


def test_deeds_and_feelings_weigh_once_a_day(game):
    npc = someone(game)
    kind = {"kind": "deed", "text": "You helped an old woman.", "tone": "kind"}
    glad = {"kind": "feeling", "who": npc.name, "feeling": "grateful", "strength": 0.5}
    commit(game.world, accept(scene(game), [kind, glad]).events)
    again = accept(scene(game), [kind, glad])
    assert again.events == [] and [why for _, why in again.rejected] == ["one deed a day",
                                                                          "they have felt enough today"]
    advance(game.world, 4)  # the next day
    assert len(accept(scene(game), [kind, glad]).events) == 2


def test_the_same_newcomer_line_twice_at_one_moment_is_two_people(game):
    new = {"kind": "minor_npc", "occupation": "tea seller", "traits": ["kind"]}
    before = len(people_at(game.world, game.place.id))
    commit(game.world, accept(scene(game, salt="same"), [new]).events)
    commit(game.world, accept(scene(game, salt="same"), [new]).events)
    assert len(people_at(game.world, game.place.id)) == before + 2


def test_a_turn_that_fails_after_its_changes_takes_them_back(game, monkeypatch):
    npc, me = someone(game), game.player.id
    mine = silver_of(game.world, me)
    rest = Choice("Rest a while", Action("rest"))
    t, (w, reply) = asked(game, {"prose": "You pay and rest.", "proposals": [
        {"kind": "pay", "to": npc.name, "amount": 1}, {"kind": "action", "choice": "Rest a while"}]},
        "I pay and rest.", [rest])

    def broken(_target):
        raise RuntimeError("the rest broke")
    monkeypatch.setattr(game, "_do_rest", broken)
    with pytest.raises(RuntimeError):
        t.resolve(game, w, reply, [rest], "assist")
    assert silver_of(game.world, me) == mine  # the payment went back with the turn


def test_in_ai_only_an_actions_own_lines_are_shown_and_only_the_change_lines_hidden(game):
    npc = someone(game)
    rest = Choice("Rest a while", Action("rest"))
    t, (w, reply) = asked(game, {"prose": "You sit.", "proposals": [
        {"kind": "feeling", "who": npc.name, "feeling": "amused", "strength": 0.2},
        {"kind": "action", "choice": "Rest a while"}]}, "I sit and rest.", [rest], mode="ai_only")
    turn, lines = t.resolve(game, w, reply, [rest], "ai_only")
    assert lines[0] == ("You sit.", "prose") and len(lines) > 1
    assert (f"{npc.name} is amused.", "dim") not in lines  # the change's own line is the hidden one


def test_a_name_with_a_possessive_is_a_name_the_turn_carries(game):
    npc = someone(game)
    assert refusal(game.world, f"{npc.name}'s eyes narrow.", game.player.id, game.place.id,
                   f"TALKING TO: {npc.name}") is None


def test_check_ai_reads_only_what_is_new(game):
    world = game.world
    with world.transaction():
        world._conn.executemany("insert into chronicle(time, kind, actors, place, data) values (?, ?, ?, ?, ?)",
                                [(0, "talked", "[]", None, '{"ai": true, "summary": "x"}')] * 20_000)
    check_ai(world)
    gc.collect()
    best = float("inf")
    for _ in range(5):
        began = time.perf_counter()
        check_ai(world)
        best = min(best, time.perf_counter() - began)
    assert best < 0.005
    npc = someone(game)
    from world.events import Event
    commit(world, [Event("ai_felt", (game.player.id, npc.id), game.place.id,
                         {"feeling": "fear", "strength": 0.9, "ai": True, "proposal": {}})])
    assert any("feeling past its limits" in p for p in check_ai(world))  # what is new is still checked


def test_a_conversations_lines_are_forgotten_at_farewell_and_with_the_game(tmp_path):
    app = App(Config(ai_mode="assist"), tmp_path / "saves", tmp_path / "settings.json", logs_dir=tmp_path / "logs",
              bridge=FakeClaude(*[None] * 20))
    app.start_new("Mo Rin", world_seed=11, creation=CreationChoice("origin", "hunter"))
    app.state = "game"
    npc = people_at(app.game.world, app.game.place.id, exclude=app.game.player.id)[0]
    app._show(app.game.perform(Action("talk", npc.id)))
    app.typed.talk = (npc.id, ["You: Hello.", f"{npc.name}: Well met."])
    app.submit("bye")
    assert app.typed.talk == (None, [])
    app.typed.talk, app.typed.last = (npc.id, ["You: Hello."]), {"job": "dialogue"}
    app._close_game()
    assert app.typed.talk == (None, []) and app.typed.last == {}
    app.shutdown()
