import json
import time

from ai.fake import FakeClaude
from ai.guard import refusal
from ai.narrate import WAITING
from app import App
from config import Config
from engine.actions import Action
from engine.game import Game
from systems.creation import CreationChoice

MIST = {"prose": "Mist hangs over the reeds, and the town wakes slowly around you."}


def make_app(tmp_path, *replies, mode="assist", available=True):
    fake = FakeClaude(*replies, available=available)
    app = App(Config(ai_mode=mode), tmp_path / "saves", tmp_path / "settings.json", bridge=fake)
    app.start_new("Mo Rin", world_seed=11, creation=CreationChoice("origin", "hunter"))
    app.state = "game"
    return app, fake


def wait(app):
    for _ in range(300):
        pending = app.narration.pending
        if pending is None or pending.future.done():
            app.poll()
            return
        time.sleep(0.01)
    raise AssertionError("no reply came")


def turn_texts(app, turn_start):
    return [text for text, _ in app.log[turn_start:]]


def test_a_turn_marks_the_lines_its_narrator_wrote(tmp_path):
    fresh = Game.new(tmp_path / "f.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    turn = fresh.start()
    assert turn.narrated and turn.lines[turn.narrated[0]][0].startswith("Crimson Town stands on stilts")
    assert any(line[0].startswith("Here:") for i, line in enumerate(turn.lines) if i not in turn.narrated)
    rest = fresh.perform(Action("rest"))
    assert rest.narrated == list(range(len(rest.lines)))  # a rest is all the narrator's
    fresh.close()


def test_off_asks_nothing(tmp_path):
    app, fake = make_app(tmp_path, MIST, mode="off")
    app.submit("look")
    app.poll()
    assert fake.calls == [] and not any(key == "prose" for _, key in app.log)
    app.shutdown()


def test_assist_shows_procedural_text_then_claudes_prose_in_its_place(tmp_path):
    app, fake = make_app(tmp_path, MIST)
    turn = app.last_turn  # the opening turn
    assert app.log[:len(turn.lines)] == turn.lines  # procedural first
    wait(app)
    narrated = [turn.lines[i] for i in turn.narrated]
    kept = [line for i, line in enumerate(turn.lines) if i not in turn.narrated]
    at = turn.narrated[0]
    assert app.log[:len(kept) + 1] == kept[:at] + [(MIST["prose"], "prose")] + kept[at:]  # in its place
    assert not any(line in app.log for line in narrated)
    assert "STATE:" in fake.calls[-1][1] and "EVENT:" in fake.calls[-1][1]
    app.shutdown()


def test_ai_only_hides_the_text_until_the_prose_comes_and_restores_it_on_failure(tmp_path):
    app, fake = make_app(tmp_path, MIST, None, mode="ai_only")
    assert WAITING in app.log
    wait(app)
    assert WAITING not in app.log and (MIST["prose"], "prose") in app.log
    app.submit("rest")
    turn = app.last_turn
    assert WAITING in app.log and not any(turn.lines[i] in app.log for i in turn.narrated)
    wait(app)  # the scripted failure
    assert WAITING not in app.log and all(turn.lines[i] in app.log for i in turn.narrated)
    app.shutdown()


def test_acting_before_the_prose_comes_puts_the_text_back(tmp_path):
    slow = lambda job, prompt: (time.sleep(0.3), MIST)[1]  # noqa: E731
    app, fake = make_app(tmp_path, slow, slow, mode="ai_only")
    first = app.last_turn
    app.submit("rest")  # the opening turn's prose has not come
    assert all(first.lines[i] in app.log for i in first.narrated)
    wait(app)
    assert app.log.count((MIST["prose"], "prose")) == 1  # only the turn still waiting got it
    app.shutdown()


def test_prose_that_brings_in_a_stranger_or_a_number_is_refused(tmp_path):
    stranger = {"prose": "Gu Nobody watches you from the reeds."}
    app, fake = make_app(tmp_path, stranger)
    app.game.world.add_entity("person", "Gu Nobody", {"occupation": "monk", "traits": [], "realm": "mortal",
                                                      "portrait": {"hair": 0, "face": 0, "robe": 0}}, "test:ai:gu")
    wait(app)
    assert ("Gu Nobody watches you from the reeds.", "prose") not in app.log
    assert "Gu Nobody" in app.narration.refused
    world, me, here = app.game.world, app.game.player.id, app.game.place.id
    assert refusal(world, "You pay 40 silver.", me, here, "OUTCOME: you pay 30 silver") == \
        "it states 40, which the turn did not"
    assert refusal(world, "You pay the man.", me, here, "you pay 30 silver", "You pay 30 silver.") == \
        "it leaves out the 30 the turn told"
    assert refusal(world, "You pay 30 silver.", me, here, "you pay 30 silver", "You pay 30 silver.") is None
    app.shutdown()


def test_prose_wrapped_twice_is_unwrapped():
    from ai.narrate import unwrap
    assert unwrap('{"prose": "You cast your gaze about."}') == "You cast your gaze about."
    assert unwrap("  Plain words.  ") == "Plain words."
    assert unwrap("{not json") == "{not json"


def test_the_same_turn_is_not_asked_twice(tmp_path):
    app, fake = make_app(tmp_path, MIST)
    wait(app)
    calls = len(fake.calls)
    turn = app.last_turn
    app.log.extend(turn.lines)
    app.narration.start(app.log, len(app.log) - len(turn.lines), turn, app.game)
    assert len(fake.calls) == calls and app.log[-len(turn.lines):].count((MIST["prose"], "prose")) == 1
    app.shutdown()


def test_f1_cycles_the_mode_and_remembers_it(tmp_path):
    app, fake = make_app(tmp_path, mode="off")
    cycle_mode(app)
    assert app.narration.mode == "assist" and app.log[-1] == ("AI prose: procedural first, then Claude's.", "system")
    cycle_mode(app)
    cycle_mode(app)
    assert app.narration.mode == "off"
    cycle_mode(app)
    assert json.loads((tmp_path / "settings.json").read_text())["ai_mode"] == "assist"
    app.shutdown()


def test_without_claude_the_modes_stay_off_and_say_why(tmp_path):
    app, fake = make_app(tmp_path, mode="off", available=False)
    cycle_mode(app)
    assert app.narration.mode == "off"
    assert app.log[-1] == ("Claude's prose cannot be used: the claude command is not installed.", "system")
    app.shutdown()


def test_a_pause_is_told_once(tmp_path):
    app, fake = make_app(tmp_path, MIST)
    wait(app)
    fake.just_paused = True
    app.poll()
    app.poll()
    assert sum("rests for five minutes" in text for text, _ in app.log) == 1
    app.shutdown()


def cycle_mode(app):
    """F1 opens the AI menu (phase 6b); its first line cycles the mode; Esc closes it."""
    app.handle_key("f1", "")
    app.handle_key("1", "1")
    app.handle_key("escape", "\x1b")
