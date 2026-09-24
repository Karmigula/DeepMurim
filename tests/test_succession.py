import pytest

import systems.agendas as agendas
import systems.encounters as encounters
import systems.lives as lives
import systems.sect as sect_mod
from app import App
from config import Config
from debug.invariants import check_lineage, check_world
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.creation import CreationChoice
from systems.purse import silver_of
from systems.techniques import known_arts, martial_arts
from tests.test_sect import found_sect


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
    for name in ("MARRY_CHANCE", "BIRTH_CHANCE", "MOVE_CHANCE", "REVENGE_CHANCE", "APPRENTICE_CHANCE"):
        monkeypatch.setattr(agendas, name, 0.0)


def local(game, path, **data):
    return founding.make_person(game.world, path, game.place.id, **{"occupation": "herbalist", **data})


def die(game, monkeypatch):
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 1.0)
    turn = game.perform(Action("meditate", 90))
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    return turn


def texts(turn):
    return [t for t, _ in turn.lines]


def test_heirs_are_offered_on_the_death_screen(game, monkeypatch):
    son = local(game, "test:son", age=20, gender="man")
    agendas._pair(game.world, game.player.id, son, "child")
    turn = die(game, monkeypatch)
    assert [c.action.verb for c in turn.choices] == ["succeed", "newcomer", "new_world"]
    assert turn.choices[0].action.target == son and "your son" in turn.choices[0].label


def test_with_no_heir_only_a_fresh_start_is_offered(game, monkeypatch):
    turn = die(game, monkeypatch)
    assert [c.action.verb for c in turn.choices] == ["newcomer", "new_world"]


def test_a_child_inherits_everything(game, monkeypatch):
    world, old = game.world, game.player.id
    son = local(game, "test:son", age=20)
    agendas._pair(world, old, son, "child")
    world.update_data(old, silver=1000)
    token = world.add_entity("item", "Jade Token", {"kind": "curio"})
    world.relate(old, token, "owns")
    arts = {a.technique.id: a.completeness for a in martial_arts(world, old)}
    die(game, monkeypatch)
    turn = game.perform(Action("succeed", son))
    assert world.get_meta("player_id") == son and game.player.id == son
    assert world.entity(son).data["silver"] >= 1000 and world.entity(old).data["silver"] == 0
    assert world.targets(son, "owns") == [token] and world.targets(old, "owns") == []
    theirs = {a.technique.id: a.completeness for a in known_arts(world, son)}
    assert all(theirs[t] == pytest.approx(round(c * 0.7, 3)) for t, c in arts.items())
    assert world.entity(son).data["ancestors"] == [old]
    assert world.facts(predicate="heir_of", subject=son)[0].object == old
    assert not world.entity(old).data.get("is_player") and not world.entity(old).data.get("dying")
    assert check_lineage(world) == []
    assert any("You are" in t for t in texts(turn))


def test_a_follower_inherits_less(game, monkeypatch):
    world, old = game.world, game.player.id
    follower = local(game, "test:follower", age=30, sworn_to=old)
    world.update_data(old, silver=1000)
    arts = {a.technique.id: a.completeness for a in martial_arts(world, old)}
    die(game, monkeypatch)
    before = silver_of(world, follower)  # NPCs carry a seeded purse
    left = world.entity(old).data["silver"]  # what the dead player held at the end
    game.perform(Action("succeed", follower))
    assert silver_of(world, follower) == before + int(left * 0.5)
    theirs = {a.technique.id: a.completeness for a in known_arts(world, follower)}
    assert all(theirs[t] == pytest.approx(round(c * 0.3, 3)) for t, c in arts.items())
    assert not world.entity(follower).data.get("sworn_to")


def test_the_sect_and_its_land_pass_to_the_heir(game, monkeypatch):
    sect, town = found_sect(game)
    world, old = game.world, game.player.id
    disciple = sect_mod.members(world, sect)[0]
    world.update_data(disciple, age=25)
    die(game, monkeypatch)
    game.perform(Action("succeed", disciple))
    assert world.entity(sect).data["founder"] == disciple
    assert founding.my_sect(world, disciple) == sect
    assert world.targets(disciple, "owns_land") == [town] and world.targets(old, "owns_land") == []
    assert [p for p in check_world(world) if "sect" in p or "leader" in p] == []


def test_an_heir_away_on_duty_wakes_at_the_seat(game, monkeypatch):
    sect, town = found_sect(game)
    world = game.world
    disciple = sect_mod.members(world, sect)[0]
    world.update_data(disciple, age=25)
    game._commit(sect_mod.duty_events(world, game.player.id, disciple, town, True))
    die(game, monkeypatch)
    turn = game.perform(Action("succeed", disciple))
    assert world.targets(disciple, "located_in") == [town] and not world.entity(disciple).data["on_duty"]
    assert any(t.startswith("Here:") for t in texts(turn))


def test_a_newcomer_starts_in_the_same_world(tmp_path, monkeypatch):
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new("First", world_seed=11)
    old = app.game.player.id
    save = app.save_path
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 1.0)
    app.submit("meditate season")
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    app.submit(str(next(i for i, c in enumerate(app.choices, 1) if c.action.verb == "newcomer")))
    assert app.state == "name"
    for ch in "Second":
        app.handle_key(ch, ch)
    app.handle_key("return", "\r")
    app.handle_key("return", "\r")
    assert app.state == "game" and app.save_path == save
    world = app.game.world
    assert app.game.player.id != old and app.game.player.name == "Second"
    assert world.entity(old).data["dead"] and not world.entity(old).data.get("is_player")
    assert check_lineage(world) == [] and not world.entity(app.game.player.id).data.get("ancestors")
    app.shutdown()
    again = Game.load(save)
    assert again.start().choices and again.player.name == "Second"
    again.close()
