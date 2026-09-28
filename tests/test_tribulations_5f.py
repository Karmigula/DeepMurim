import pytest

import systems.demons as D
import systems.encounters as encounters
import systems.karma as K
import systems.lives as lives
import systems.tribulations as TR
from debug.invariants import check_karma
from engine.game import Game
from systems import founding
from systems.creation import CreationChoice
from world.events import Event, commit


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


def test_a_great_tribulation_grows_with_the_realm_and_a_minor_one_is_one_wave(game):
    world, me = game.world, game.player.id
    assert TR.plan(world, me, 3, False) == {"realm": 3, "minor": False, "strength": 3.0, "waves": ["lightning"] * 2}
    assert TR.plan(world, me, 7, False)["waves"] == ["lightning", "fire"] * 3
    assert TR.plan(world, me, 2, True)["waves"] == ["lightning"]


def test_sin_adds_waves_and_weight_and_merit_lightens_them(game):
    world, me = game.world, game.player.id
    K.write(world, me, sin=250.0)
    heavy = TR.plan(world, me, 3, False)
    assert len(heavy["waves"]) == 4 and heavy["strength"] == 8.0
    K.write(world, me, sin=0.0, merit=150.0)
    assert TR.plan(world, me, 3, False)["strength"] == 1.5


def test_a_carried_demon_comes_as_a_wave(game):
    world, me = game.world, game.player.id
    D.add_demon(world, me, "grief", 5, 2)
    assert TR.plan(world, me, 4, False)["waves"] == ["lightning", "demon", "lightning", "lightning"]


def test_a_gathering_tribulation_waits_over_the_player(game):
    world, me = game.world, game.player.id
    commit(world, TR.gather_events(world, me, game.place.id, 3, False, "breakthrough"))
    assert TR.pending(world, me) == {"realm": 3, "minor": False, "strength": 3.0, "waves": ["lightning"] * 2,
                                     "wave": 0, "failed": []}
    assert check_karma(world) == []


def test_heaven_takes_notice_of_heavy_sin_once_a_year(game):
    world, me = game.world, game.player.id
    assert TR.season_hook(world, 0) == []
    K.write(world, me, sin=200.0)
    [event] = TR.season_hook(world, 0)
    assert event.kind == "tribulation_gathers" and event.data["minor"] and event.data["why"] == "notice"
    world.set_time(world.time + lives.SEASON)
    assert TR.season_hook(world, 1) == []
    world.set_time(world.time + 4 * lives.SEASON)
    assert TR.season_hook(world, 5)


def test_the_lightning_can_kill_the_wicked_and_it_is_news(game):
    world, town = game.world, game.place.id
    n = world.time // lives.SEASON
    fiends = []
    for i in range(30):
        fiend = founding.make_person(world, f"test:fiend:{i}", town, occupation="monk", age=50, realm="second-rate")
        K.write(world, fiend, sin=600.0, merit=0.0)
        fiends.append(fiend)
    assert TR.npc_death_chance(world, fiends[0]) == TR.NPC_DEATH_MAX
    for fiend in fiends:
        commit(world, [Event("broke_through", (fiend,), town, {"realm": 3, "season": n})])
    dead = [f for f in fiends if world.entity(f).data.get("dead")]
    assert 5 <= len(dead) <= 25 and world.facts(predicate="fell_to_tribulation", subject=dead[0])


def test_check_karma_flags_a_malformed_tribulation(game):
    world, me = game.world, game.player.id
    world.update_data(me, tribulation={"realm": 3, "minor": False, "strength": 0.2, "waves": ["hail"], "wave": 0,
                                       "failed": []})
    assert "tribulation" in " | ".join(check_karma(world))
