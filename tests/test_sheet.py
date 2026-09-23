from app import App
from config import Config
from engine.game import Game
from engine.sheet import sheet_lines
from render.body_chart import body_chart
from render.screen import FALLBACK
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from world.body import add_injury


def test_sheet_shows_numbers_but_never_hidden_truths(tmp_path):
    game = Game.new(tmp_path / "g.world", "Hero", world_seed=3, creation=CreationChoice("origin", "scion"))
    body = load_body(game.world, game.player.id)
    body.constitution, body.constitution_known = "Nine Yin Body", False
    save_body(game.world, game.player.id, body)
    text = "\n".join(t for t, _ in sheet_lines(game.world, game.player.id))
    for heading in ("Realm: Mortal", "Arts:", "Meridians:", "Injuries:"):
        assert heading in text
    assert "completeness 100%" in text and "80%" not in text  # the family method looks whole
    assert "Constitution: unknown" in text and "Nine Yin" not in text
    game.close()


def test_body_chart_colours_injured_parts(tmp_path):
    game = Game.new(tmp_path / "g.world", "Hero", world_seed=3)
    body = load_body(game.world, game.player.id)
    add_injury(body, "left arm", "fracture", 5, 0, "x", permanent=True)
    art = body_chart(body, 0, 40, 18)
    assert len(art) == 18 and all(len(r) == 40 for r in art)
    colours = {cell[1] for row in art for cell in row if cell}
    assert "purple" in colours and "green" in colours
    tiny = body_chart(body, 0, 5, 3)
    assert len(tiny) == 3 and all(len(r) == 5 for r in tiny)
    game.close()


def test_symbols_have_font_fallbacks():
    for symbol in "●◐◌×·":
        assert symbol in FALLBACK


def test_f4_toggles_the_sheet(tmp_path):
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new("Hero", world_seed=3)
    app.handle_key("f4", "")
    text = "\n".join("".join(c[0] if c else " " for c in row) for row in app.grid(120, 40))
    assert "CHARACTER SHEET" in text and "Arts:" in text
    app.handle_key("f12", "")
    assert app.sheet_visible is False and app.debug_visible
    app.handle_key("f4", "")
    assert app.sheet_visible and not app.debug_visible
    app.handle_key("f4", "")
    assert not app.sheet_visible
    app.shutdown()
