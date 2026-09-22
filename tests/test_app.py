import pytest

from app import App
from config import Config


@pytest.fixture
def app(tmp_path):
    a = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    yield a
    a.shutdown()


def type_text(app, text):
    for ch in text:
        app.handle_key(ch, ch)


def new_game(app, name="Mo Rin"):
    assert app.title_options()[0] == "New world"
    app.handle_key("return", "\r")
    assert app.state == "name"
    type_text(app, name)
    app.handle_key("return", "\r")
    assert app.state == "game"


def test_new_game_flow(app):
    assert app.title_options() == ["New world", "Quit"]
    new_game(app)
    assert app.log and app.choices
    before = len(app.log)
    app.handle_key("1", "1")  # digit with empty command picks a choice
    assert len(app.log) > before
    assert len(app.grid(100, 30)) == 30


def test_typed_command_and_unknown(app):
    new_game(app)
    type_text(app, "dance wildly")
    app.handle_key("return", "\r")
    assert any("Not understood" in text for text, _ in app.log)
    assert app.command == ""


def test_f2_swaps_side_and_persists(app, tmp_path):
    new_game(app)
    app.handle_key("f2", "")
    assert app.config.art_side == "right"
    assert '"right"' in (tmp_path / "settings.json").read_text()
    app.handle_key("f3", "")
    assert app.config.show_art is False


def test_escape_to_title_then_continue(app):
    new_game(app)
    app.handle_key("escape", "\x1b")
    assert app.state == "title"
    assert app.title_options()[0] == "Continue"
    app.handle_key("return", "\r")
    assert app.state == "game" and app.choices


def test_corrupt_save_shows_message(app, tmp_path):
    saves = tmp_path / "saves"
    saves.mkdir()
    (saves / "broken.world").write_bytes(b"garbage" * 50)
    assert app.title_options()[0] == "Continue"
    app.handle_key("return", "\r")
    assert app.state == "title" and app.message
