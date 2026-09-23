import pytest

from app import App
from config import Config
from engine.actions import Action
from engine.game import Game
from engine.standing_page import faction_facts, known_factions, standing_lines
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def join_first_sect(game):
    sect = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(game.world, sect)
    game.world.relate(game.player.id, sect, "member_of", 1, {
        "role": "member", "hall": 0, "sponsor": halls.elders(game.world, sect)[0], "merit": 40, "secret": False,
        "joined_at": 0, "status": "member", "judged": [], "stipend_at": 0})
    return sect, seat


def test_only_known_factions_are_listed(game):
    known = known_factions(game.world, game.player.id, game.place.id)
    assert set(known) == set(halls.halls_here(game.world, game.place.id))
    sect, _ = join_first_sect(game)
    assert sect in known_factions(game.world, game.player.id, game.place.id)


def test_the_page_shows_rank_merit_and_how_factions_see_you(game):
    sect, _ = join_first_sect(game)
    text = [t for t, _ in standing_lines(game.world, game.player.id, game.place.id)]
    name = game.world.entity(sect).name
    assert "Your factions:" in text
    assert any(t.startswith(f"  {name}: inner disciple, 40 merit") for t in text)
    assert any(t.startswith(f"  {name}: welcome") for t in text)


def test_typing_standing_and_f6_show_the_page(game, tmp_path):
    turn = game.perform(Action("standing"))
    assert turn.lines[0] == ("Your standing", "heading")
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new("Paged", world_seed=11)
    app.handle_key("f6", "")
    assert any("Your standing" in text for text, _ in app.log)
    app.shutdown()


def test_briefs_mention_your_rank(game):
    sect, seat = join_first_sect(game)
    facts = faction_facts(game.world, game.player.id, None)
    assert facts == [f"You are an inner disciple of the {game.world.entity(sect).name}."]
