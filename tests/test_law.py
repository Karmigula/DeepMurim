import pytest

import systems.encounters as encounters
import systems.law as law
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from systems.membership import refusal
from systems.purse import silver_of


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def killed_here(game, n=1):
    for i in range(n):
        victim = game.world.add_entity("person", f"Hu Mei{i}", {"realm": "mortal", "occupation": "innkeeper"})
        record_fact(game.world, game.player.id, "killed", victim, place=game.place.id,
                    variant=make_variant("killed", game.player.id, victim, place=game.place.name))


def constable(game):
    bureau = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == "imperial")
    pid = game.world.add_entity("person", "Law Bao", {"realm": "third-rate", "occupation": "constable",
                                                      "traits": ["honest", "proud"]})
    game.world.relate(pid, game.place.id, "located_in")
    game.world.relate(pid, bureau, "member_of", 0, {"role": "member", "status": "member"})
    return pid


def test_a_killing_puts_a_price_on_your_head_in_towns_that_heard(game):
    assert law.bounty(game.world, game.place.id, game.player.id) == 0
    killed_here(game)
    assert law.bounty(game.world, game.place.id, game.player.id) == round(20 * 3 * 0.85)


def test_robbing_a_bandit_is_no_crime(game):
    bandit = game.world.add_entity("person", "Ma Bo", {"realm": "mortal", "occupation": "bandit"})
    record_fact(game.world, game.player.id, "robbed", bandit, place=game.place.id,
                variant=make_variant("robbed", game.player.id, bandit))
    assert law.bounty(game.world, game.place.id, game.player.id) == 0


def test_a_constable_arrests_and_a_fine_settles_it(game, monkeypatch):
    monkeypatch.setattr(law, "ARREST_CHANCE", 1.0)
    killed_here(game)
    constable(game)
    turn = game.perform(Action("look"))
    assert game.player.data["arrest"] and [c.action.verb for c in turn.choices] == ["arrest"] * 4
    game.world.update_data(game.player.id, silver=100)
    game.perform(Action("arrest", "pay"))
    assert silver_of(game.world, game.player.id) == 100 - 51
    assert law.bounty(game.world, game.place.id, game.player.id) == 0 and game.player.data.get("arrest") is None


def test_serving_time_passes_days(game, monkeypatch):
    monkeypatch.setattr(law, "ARREST_CHANCE", 1.0)
    killed_here(game)
    constable(game)
    game.perform(Action("look"))
    before = game.world.time
    game.perform(Action("arrest", "jail"))
    assert game.world.time >= before + (51 // 5) * 4 and law.bounty(game.world, game.place.id, game.player.id) == 0


def test_an_arrest_survives_a_reload(game, monkeypatch):
    monkeypatch.setattr(law, "ARREST_CHANCE", 1.0)
    killed_here(game)
    constable(game)
    game.perform(Action("look"))
    path = game.world.path
    game.close()
    again = Game.load(path)
    assert [c.action.verb for c in again.look().choices] == ["arrest"] * 4
    again.close()


def test_bounty_hunters_wait_on_the_roads(game, monkeypatch):
    monkeypatch.setattr(law, "HUNTER_CHANCE", 1.0)
    killed_here(game, n=2)
    events = law.bounty_hunter_encounter(game.world, game.player.id, game.world.entity(game.place.id), None)
    assert events and events[0].data["kind"] == "bounty_hunter"


def test_the_bureau_refuses_the_wanted(game):
    bureau = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == "imperial")
    game.world.update_data(game.player.id, realm="third-rate")
    assert refusal(game.world, game.player.id, bureau, game.place.id) is None
    killed_here(game)
    assert refusal(game.world, game.player.id, bureau, game.place.id) is not None  # distrusted, or not clean
