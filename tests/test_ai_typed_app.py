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
