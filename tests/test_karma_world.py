import pytest

import systems.encounters as encounters
import systems.karma as K
import systems.karma_world as KW
from engine.game import Game
from systems import founding
from systems.bodies import load_body
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.events import commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.update_data(g.player.id, silver=1000)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def person(game, tag, **data):
    return founding.make_person(game.world, f"test:kw:{tag}", game.place.id, **{"occupation": "bandit", "age": 40,
                                                                               **data})


def test_heaven_strikes_down_the_wicked_and_it_is_news(game, monkeypatch):
    world = game.world
    monkeypatch.setattr(KW, "STRUCK_CHANCE", 1.0)
    wicked, decent = person(game, "wicked"), person(game, "decent", occupation="monk")
    K.write(world, wicked, sin=120.0, merit=0.0)
    K.write(world, decent, sin=0.0, merit=40.0)
    assert KW.season_events(world, decent, 0, None) == []
    events = KW.season_events(world, wicked, 0, None)
    assert [e.data["cause"] for e in events] == ["heaven"]
    commit(world, events)
    assert world.entity(wicked).data.get("dead") and world.facts(predicate="struck_down", subject=wicked)


def test_a_heavy_sinners_luck_turns(game, monkeypatch):
    world, me = game.world, game.player.id
    monkeypatch.setattr(KW, "MISFORTUNE_CHANCE", 1.0)
    assert KW.season_hook(world, 0) == []
    K.write(world, me, sin=300.0)
    whats = set()
    for n in range(20):
        events = KW.season_hook(world, n)
        commit(world, events)
        whats |= {e.data["what"] for e in events}
    assert whats == {"purse", "injury"} and silver_of(world, me) < 1000
    assert any(i.cause == "a fall no one saw coming" for i in load_body(world, me).injuries)


def test_a_temple_takes_alms_for_merit_up_to_a_season_cap(game):
    world, me, here = game.world, game.player.id, game.place.id
    if not KW.has_temple(world, here):
        person(game, "abbot", occupation="monk")
    assert KW.alms_block(world, me, here, 5) == "Alms are 10 silver or more, from what you carry."
    commit(world, KW.alms_events(world, me, here, 200))
    assert K.karma_of(world, me)["merit"] == 20 and silver_of(world, me) == 800
    commit(world, KW.alms_events(world, me, here, 200))
    assert K.karma_of(world, me)["merit"] == KW.ALMS_CAP and silver_of(world, me) == 600


def test_no_monk_no_temple(game):
    world = game.world
    town = world.add_entity("town", "Empty Town", {"x": 99, "y": 99, "index": 0, "kind": "village"})
    assert not KW.has_temple(world, town)
    assert KW.alms_block(world, game.player.id, town, 50) == "There is no temple here."
