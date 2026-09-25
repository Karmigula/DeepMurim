import pytest

import systems.encounters as encounters
import systems.secret_realms as SR
import systems.sky as sky
import systems.world_events as W
from engine.game import Game
from systems.creation import CreationChoice
from world.events import commit
from world.seed import rng_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.set_time(10 * W.SEASON + 8)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def test_every_world_has_three_ancient_realms(game):
    world = game.world
    realms = [world.entity(r) for r in SR.ensure_realms(world)]
    assert len(realms) == SR.ANCIENT and all(r.kind == "secret_realm" and r.data["ancient"] for r in realms)
    for realm in realms:
        floors = realm.data["floors"]
        assert 3 <= len(floors) <= 6 and all(2 <= len(f) <= 4 for f in floors)
        assert all(f[-1]["kind"] == "stair" for f in floors[:-1]) and floors[-1][-1]["kind"] == "inheritance"
        assert realm.data["rule"]["kind"] in ("ceiling", "token", "quota")
        assert realm.data["next_opening"] > world.time // W.SEASON and 12 <= realm.data["period"] <= 40
        assert world.entity(realm.data["master"]["art"]).kind == "technique"
    assert SR.ensure_realms(world) == SR.realms(world) == [r.id for r in realms]  # seeded once


def test_a_look_makes_no_realms(game):
    game.perform(__import__("engine.actions", fromlist=["Action"]).Action("look"))
    assert SR.realms(game.world) == []  # the season clock seeds them; a read never writes


def test_a_realms_layout_is_the_same_for_the_same_world(tmp_path):
    def layouts(name):
        g = Game.new(tmp_path / f"{name}.world", "Hero", world_seed=7, creation=CreationChoice("origin", "hunter"))
        found = [(g.world.entity(r).name, g.world.entity(r).data["floors"], g.world.entity(r).data["rule"])
                 for r in SR.ensure_realms(g.world)]
        g.close()
        return found
    assert layouts("a") == layouts("b")


def test_an_old_save_gets_its_realms_with_openings_still_ahead(tmp_path):
    from world.db import World
    world = World.create(tmp_path / "old.world", 11)  # a world from before 4f: nothing has asked for realms yet
    world.set_time(40 * W.SEASON)
    assert all(world.entity(r).data["next_opening"] > 40 for r in SR.ensure_realms(world))
    world.close()


def test_a_missed_opening_rolls_on_to_its_next_turn(game):
    world = game.world
    realm = SR.ensure_realms(world)[0]
    period = world.entity(realm).data["period"]
    world.update_data(realm, next_opening=5)
    assert realm not in SR.due(world, 5 + period + 1)
    assert world.entity(realm).data["next_opening"] == 5 + 2 * period


def test_a_realm_opens_on_its_own_period(game):
    world = game.world
    realm = SR.ensure_realms(world)[0]
    n = world.time // W.SEASON + 1
    world.update_data(realm, next_opening=n)
    events = [e for e in sky.season_events(world, n) if e.kind == "sky_started" and e.data["type"] == "realm_opening"]
    assert [e.place for e in events] == [world.entity(realm).data["gate"]]
    assert events[0].data["data"] == SR.opening_data(realm)
    commit(world, events)
    assert world.entity(realm).data["next_opening"] == n + world.entity(realm).data["period"]
    assert SR.opening_of(world, realm) == W.index(world)[-1][W.ID]


def test_a_treasure_light_may_crack_a_newborn_realm_open(game, monkeypatch):
    import systems.events.treasure_light as tl
    monkeypatch.setattr(SR, "CRACK_CHANCE", 1.0)
    world, town = game.world, game.place.id
    before = SR.ensure_realms(world)
    commit(world, sky.start_events(world, "treasure_light", town, world.time,
                                   tl.start_data(world, town, 10, rng_for(1, "t"))))
    newborn = [r for r in SR.ensure_realms(world) if r not in before]
    assert len(newborn) == 1
    realm = world.entity(newborn[0])
    assert not realm.data["ancient"] and realm.data["gate"] == town and realm.data["rule"]["kind"] in ("open", "token")
    assert 3 <= len(realm.data["floors"]) <= 4
    assert SR.opening_of(world, realm.id) is not None  # its first opening begins at once
    world.set_time(world.time + 4 * 4)
    ids = sky.observe(world, town)
    assert not any(world.chronicle_entry(i).kind == "race_called" for i in ids)  # the light's treasure is the realm


def test_a_one_off_realm_opens_once(game, monkeypatch):
    import systems.events.treasure_light as tl
    monkeypatch.setattr(SR, "CRACK_CHANCE", 1.0)
    monkeypatch.setattr(SR, "ONE_OFF_CHANCE", 1.0)
    world, town = game.world, game.place.id
    commit(world, sky.start_events(world, "treasure_light", town, world.time,
                                   tl.start_data(world, town, 10, rng_for(1, "t"))))
    realm = SR.ensure_realms(world)[-1]
    assert world.entity(realm).data["period"] is None and world.entity(realm).data["next_opening"] is None
    assert all(realm not in SR.due(world, n) for n in range(10, 80))
