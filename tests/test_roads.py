import pytest

import systems.encounters as encounters
from engine.game import Action, Game
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.events import commit
from world.gen.materialize import region_of


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "merchant"))
    g.start()
    yield g
    g.close()


def meet(game, kind="bandit", toll=10):
    region = region_of(game.world, game.place.id)
    slot = {"bandit": 90, "beast": 91, "wanderer": 92}[kind]
    person = encounters.make_roamer(game.world, region, kind, slot, 0.2)
    events = encounters.encounter_events(game.player.id, person, game.place.id, kind, toll)
    commit(game.world, events)
    game.encounter = encounters.encounter_state(events[0])
    return person


def verbs(turn):
    return [c.action for c in turn.choices]


def test_danger_is_seeded_and_home_is_safe():
    assert encounters.region_danger(5, 0, 0) == 0.1
    assert encounters.region_danger(5, 3, -2) == encounters.region_danger(5, 3, -2)
    assert all(0 <= encounters.region_danger(5, x, 1) <= 1 for x in range(20))


def test_roamers_live_in_the_region(game):
    region = region_of(game.world, game.place.id)
    wolf = encounters.make_roamer(game.world, region, "beast", 0, 0.5)
    bandit = encounters.make_roamer(game.world, region, "bandit", 1, 0.5)
    assert game.world.entity(wolf).data["beast"] and game.world.entity(wolf).name.startswith("a ")
    assert game.world.entity(bandit).data["occupation"] == "bandit"
    assert set(encounters.roamers(game.world, region.id)) == {wolf, bandit}


def test_travel_can_end_in_an_encounter_that_blocks_everything_else(game, monkeypatch):
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 1e9)
    road = next(c.action for c in game.look().all_choices if c.action.verb == "travel")
    turn = game.perform(road)
    assert game.encounter is not None and turn.choices[0].action == Action("road", "fight")
    assert "Deal with them first" in game.perform(Action("meditate", 7)).lines[-1][0]


def test_paying_the_toll(game):
    bandit = meet(game, toll=10)
    mine, theirs = silver_of(game.world, game.player.id), silver_of(game.world, bandit)
    game.perform(Action("road", "pay"))
    assert game.encounter is None
    assert silver_of(game.world, game.player.id) == mine - 10 and silver_of(game.world, bandit) == theirs + 10


def test_no_silver_no_toll(game):
    meet(game, toll=10)
    game.world.update_data(game.player.id, silver=3)
    turn = game.perform(Action("road", "pay"))
    assert game.encounter is not None and "You don't have 10 silver." == turn.lines[-1][0]


def test_beasts_do_not_talk_and_failed_talk_means_a_fight(game, monkeypatch):
    meet(game, kind="beast", toll=0)
    assert Action("road", "talk") not in verbs(game.look())
    game.encounter = None
    meet(game, kind="bandit")
    monkeypatch.setattr(encounters, "talk_succeeds", lambda *a: False)
    game.perform(Action("road", "talk"))
    assert game.encounter is None and game.combat is not None and game.combat.mode == "encounter"


def test_fleeing_the_road(game, monkeypatch):
    meet(game, kind="wanderer", toll=0)
    monkeypatch.setattr(encounters, "flee_succeeds", lambda *a: True)
    game.perform(Action("road", "flee"))
    assert game.encounter is None and game.combat is None


def test_an_unanswered_encounter_survives_a_reload(tmp_path):
    path = tmp_path / "g.world"
    game = Game.new(path, "Hero", world_seed=11)
    person = meet(game)
    game.close()
    again = Game.load(path)
    assert again.encounter == {"person": person, "kind": "bandit", "toll": 10}
    again.close()


def test_a_grudge_becomes_a_challenge(game, monkeypatch):
    hothead = game.world.add_entity("person", "Hot Wu", {"occupation": "constable", "traits": ["hot-tempered", "proud"],
                                                          "realm": "mortal", "portrait": {"hair": 0, "face": 0, "robe": 0}})
    game.world.relate(hothead, game.place.id, "located_in")
    commit(game.world, [encounters.Event("lost_patience", (game.player.id, hothead), game.place.id, {"topic": "work"},
                                         witnesses=(encounters.Witness(hothead, "annoyed", 0.5),))])
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 1.0)
    game.world.set_time(game.world.time + 4)
    turn = game.perform(Action("look"))
    assert game.challenger == hothead and [c.action.verb for c in turn.choices] == ["answer_challenge", "answer_challenge"]
    game.perform(Action("answer_challenge", False))
    assert game.challenger is None
    assert game.world.memories(hothead, about=game.player.id)[-1].feeling == "contempt"
