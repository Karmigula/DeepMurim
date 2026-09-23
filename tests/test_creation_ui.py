import json

from app import App
from config import Config
from debug.replay import replay
from systems.creation import ORIGINS


def make(tmp_path):
    return App(Config(), tmp_path / "saves", tmp_path / "settings.json")


def to_create(app, name="Hero"):
    app.handle_key("return", "\r")  # New world
    for ch in name:
        app.handle_key(ch, ch)
    app.handle_key("return", "\r")
    assert app.state == "create"


def screen(app):
    return "\n".join("".join(c[0] if c else " " for c in row) for row in app.grid(120, 40))


def test_random_is_one_keypress(tmp_path):
    app = make(tmp_path)
    to_create(app)
    assert "Random (roll everything)" in screen(app)
    app.handle_key("return", "\r")
    assert app.state == "game" and app.game.player.data["origin"] in ORIGINS
    app.shutdown()


def test_choose_an_origin(tmp_path):
    app = make(tmp_path)
    to_create(app)
    app.handle_key("down", "")
    app.handle_key("return", "\r")
    assert app.state == "origin" and "Hunter's child" in screen(app)
    app.handle_key("down", "")
    assert ORIGINS["scion"].description in screen(app)
    app.handle_key("return", "\r")
    assert app.state == "game" and app.game.player.data["origin"] == "scion"
    app.shutdown()


def test_point_buy_respects_the_pool(tmp_path):
    app = make(tmp_path)
    to_create(app)
    app.handle_key("down", "")
    app.handle_key("down", "")
    app.handle_key("return", "\r")
    assert app.state == "points"
    for _ in range(20):
        app.handle_key("right", "")  # strength: 8 -> 16, the maximum
    assert app.points["strength"] == 16
    app.handle_key("left", "")
    app.handle_key("right", "")
    app.handle_key("return", "\r")  # Enter on a stat row just moves down a row
    assert app.points_row == 1
    for _ in range(20):
        app.handle_key("right", "")  # agility: only 4 points are left
    assert app.points["agility"] == 12 and "Points left: 0" in screen(app)
    for _ in range(3):
        app.handle_key("left", "")
    assert app.points["agility"] == 9
    for _ in range(10):
        app.handle_key("down", "")  # clamps on the last row, Begin
    app.handle_key("up", "")
    app.handle_key("right", "")  # form: sword -> saber
    app.handle_key("down", "")
    app.handle_key("return", "\r")
    assert app.state == "game" and app.game.player.data["origin"] == "self_made"
    assert app.game.player.data["body"]["physique"]["agility"] == 9
    app.shutdown()


def test_escape_walks_back(tmp_path):
    app = make(tmp_path)
    to_create(app)
    app.handle_key("down", "")
    app.handle_key("return", "\r")
    app.handle_key("escape", "\x1b")
    assert app.state == "create"
    app.handle_key("escape", "\x1b")
    assert app.state == "name"


def test_session_records_creation_and_replays(tmp_path):
    app = make(tmp_path)
    to_create(app)
    app.handle_key("down", "")
    app.handle_key("return", "\r")
    app.handle_key("return", "\r")  # hunter
    for key in ("1", "1"):
        app.handle_key(key, key)
    path = app.session.path
    app.shutdown()
    header = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert header["creation"] == {"mode": "origin", "origin": "hunter", "physique": None, "flow_points": 0, "form": None}
    assert replay(path, tmp_path / "r").mismatches == []


def test_replay_of_a_migrated_old_save(tmp_path):
    app = make(tmp_path)
    app.start_new("Hero", world_seed=5)
    pid = app.game.player.id
    app.game.world._conn.execute("update entities set data = json_remove(data, '$.body') where id = ?", (pid,))
    app.game.world._conn.execute("delete from relations where a = ? and kind = 'knows'", (pid,))
    app.handle_key("escape", "\x1b")
    app.handle_key("return", "\r")  # Continue: the save is migrated as it loads
    assert app.state == "game"
    app.submit("look")
    path = app.session.path
    app.shutdown()
    assert replay(path, tmp_path / "r").mismatches == []
