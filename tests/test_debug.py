"""The bug-catching kit: invariants, crash catcher, session log, replay, bug report, overlay."""

import json


from app import App
from config import Config
from debug.invariants import check_turn, check_world
from debug.replay import replay
from engine.game import Action, Choice, Game, Turn
from world.db import World


def make_app(tmp_path):
    return App(Config(), tmp_path / "saves", tmp_path / "settings.json")


def start(app, name="Hero", seed=42):
    app.start_new(name, world_seed=seed)
    assert app.state == "game"


def press(app, *texts):
    for text in texts:
        for ch in text:
            app.handle_key(ch, ch)
        app.handle_key("return", "\r")


# --- invariants ---------------------------------------------------------------

def test_fresh_world_is_clean(tmp_path):
    game = Game.new(tmp_path / "w.world", "Hero", world_seed=42)
    turn = game.start()
    assert check_world(game.world) == []
    assert check_turn(game, turn, []) == []
    game.close()


def test_world_invariants_catch_broken_state(tmp_path):
    game = Game.new(tmp_path / "w.world", "Hero", world_seed=42)
    world = game.world
    pid = world.get_meta("player_id")
    other = world.add_entity("town", "Elsewhere", {"x": 9, "y": 9, "index": 0})
    world.relate(pid, other, "located_in")
    world._conn.execute("insert into chronicle(time, kind, actors, place, data, weight) values(-5, 'odd', '[]', null, '{}', 1)")
    problems = " | ".join(check_world(world))
    assert "2 locations" in problems
    assert "time went backwards" in problems
    game.close()


def test_turn_invariants_catch_bad_output(tmp_path):
    game = Game.new(tmp_path / "w.world", "Hero", world_seed=42)
    choices = [Choice(f"c{n}", Action("look")) for n in range(10)] + [Choice("?", Action("teleport"))]
    turn = Turn(
        [("Hello {npc}", "npc"), ("[mystery]", "dim"), ("The wind howls.", "default")],
        choices, {"type": "scene"}, "status",
    )
    problems = " | ".join(check_turn(game, turn, ["The wind howls."]))
    for expected in ("leftover", "fallback", "choices", "teleport", "repeat"):
        assert expected in problems, expected
    game.close()


# --- crash catcher --------------------------------------------------------------

def test_crash_is_caught_reported_and_survivable(tmp_path):
    app = make_app(tmp_path)
    start(app)

    def boom(action):
        raise RuntimeError("kaboom")

    real = app.game.perform
    app.game.perform = boom
    press(app, "look")
    assert app.state == "game" and app.crash_count == 1
    reports = list((tmp_path / "logs").glob("crash-*.txt"))
    assert len(reports) == 1
    text = reports[0].read_text(encoding="utf-8")
    assert "kaboom" in text and "Traceback" in text and "seed" in text
    assert any("crash report" in line for line, _ in app.log)
    app.game.perform = real
    press(app, "look")
    assert app.crash_count == 1
    app.shutdown()


# --- session log + replay -------------------------------------------------------------

def play_a_bit(app):
    press(app, "1", "1", "2", "3", "look", "look", "journal", "talk zzz", "go north", "look")


def test_session_log_records_everything(tmp_path):
    app = make_app(tmp_path)
    start(app)
    play_a_bit(app)
    entries = [json.loads(line) for line in app.session.path.read_text(encoding="utf-8").splitlines()]
    kinds = [e["kind"] for e in entries]
    assert kinds[0] == "session" and entries[0]["seed"] == 42 and entries[0]["mode"] == "new"
    assert kinds[1] == "turn"
    assert kinds.count("command") == 10 and kinds.count("turn") == 11
    app.shutdown()


def test_replay_reproduces_a_session(tmp_path):
    app = make_app(tmp_path)
    start(app)
    play_a_bit(app)
    path = app.session.path
    app.shutdown()
    result = replay(path, tmp_path / "replay1")
    assert result.commands == 10 and result.mismatches == []

    lines = path.read_text(encoding="utf-8").splitlines()
    last_turn = max(i for i, line in enumerate(lines) if json.loads(line)["kind"] == "turn")
    tampered = json.loads(lines[last_turn])
    tampered["lines"] = [["Something else entirely.", "default"]]
    lines[last_turn] = json.dumps(tampered)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert replay(path, tmp_path / "replay2").mismatches


def test_replay_of_a_continued_game(tmp_path):
    app = make_app(tmp_path)
    start(app)
    press(app, "1", "1")
    app.handle_key("escape", "\x1b")
    assert app.state == "title"
    app.handle_key("return", "\r")  # Continue
    assert app.state == "game"
    play_a_bit(app)
    path = app.session.path
    app.shutdown()
    header = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert header["mode"] == "continue"
    assert World.open(header["snapshot"]).world_seed == 42
    assert replay(path, tmp_path / "replay").mismatches == []


# --- bug report + overlay --------------------------------------------------------------

def test_f9_saves_a_bug_report_with_the_typed_note(tmp_path):
    app = make_app(tmp_path)
    start(app)
    press(app, "1")
    for ch in "npc repeats":
        app.handle_key(ch, ch)
    app.handle_key("f9", "")
    reports = list((tmp_path / "logs").glob("report-*"))
    assert len(reports) == 1
    folder = reports[0]
    assert "npc repeats" in (folder / "summary.txt").read_text(encoding="utf-8")
    assert (folder / "session.jsonl").is_file()
    assert World.open(folder / "save.world").world_seed == 42
    assert app.command == ""
    assert any("Bug report saved" in line for line, _ in app.log)
    app.shutdown()


def test_f12_toggles_debug_overlay(tmp_path):
    app = make_app(tmp_path)
    start(app)
    press(app, "1", "1")  # seed 42's town is busy: 1 opens the people list, 1 talks
    app.handle_key("f12", "")
    text = "\n".join("".join(c[0] if c else " " for c in row) for row in app.grid(120, 40))
    assert "DEBUG" in text and "seed 42" in text and "EVENT:" in text
    app.handle_key("f12", "")
    text = "\n".join("".join(c[0] if c else " " for c in row) for row in app.grid(120, 40))
    assert "DEBUG" not in text
    app.shutdown()


def test_violations_surface_in_the_log(tmp_path):
    app = make_app(tmp_path)
    start(app)
    art = app.last_turn.art
    app.game.perform = lambda action: Turn([("Hi {npc}", "npc")], app.choices, art, "s")
    press(app, "look")
    assert app.violations and any("debug:" in line for line, _ in app.log)
    app.shutdown()


def test_lowercase_sentence_start_is_a_violation(tmp_path):
    game = Game.new(tmp_path / "w.world", "Hero", world_seed=42)
    turn = Turn([('"Again? hunter," he says.', "npc")], [], {"type": "scene"}, "status")
    assert any("lowercase" in p for p in check_turn(game, turn, []))
    game.close()


def test_f9_with_empty_line_asks_for_a_note(tmp_path):
    app = make_app(tmp_path)
    start(app)
    app.handle_key("f9", "")
    assert app.state == "report"
    assert "Describe the bug" in "\n".join("".join(c[0] if c else " " for c in row) for row in app.grid(120, 40))
    for ch in "npc repeats":
        app.handle_key(ch, ch)
    app.handle_key("return", "\r")
    assert app.state == "game"
    [folder] = list((tmp_path / "logs").glob("report-*"))
    assert "npc repeats" in (folder / "summary.txt").read_text(encoding="utf-8")
    app.handle_key("f9", "")
    app.handle_key("escape", "\x1b")  # cancel: no report, back to the game
    assert app.state == "game" and len(list((tmp_path / "logs").glob("report-*"))) == 1
    app.shutdown()
