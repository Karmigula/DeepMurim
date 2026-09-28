import pytest

import systems.demons as D
import systems.encounters as encounters
import systems.heart as HT
import systems.oaths as O
import systems.reputation as reputation
from debug.invariants import check_heart
from engine.game import Game
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


def someone(game, tag):
    pid = game.world.add_entity("person", f"Someone {tag}", {"occupation": "tea seller", "traits": ["proud"],
                                                              "realm": "mortal", "age": 40}, seed_path=f"test:oath:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def swear(game, kind, whom=None):
    commit(game.world, O.swear_events(game.world, game.player.id, kind, whom, game.place.id))


def dies(game, victim, killer=None):
    commit(game.world, [Event("died", (killer or victim, victim), game.place.id, {"cause": "killed", "world": True})])


def test_what_may_be_sworn(game):
    world, me = game.world, game.player.id
    foe, friend = someone(game, "foe"), someone(game, "friend")
    assert O.swear_block(world, me, "vengeance", foe) == "You bear them no grudge to avenge."
    D.add_demon(world, me, "grudge", foe, 2)
    assert O.swear_block(world, me, "vengeance", foe) is None
    assert O.swear_block(world, me, "protection", me) == "There is no one living to swear it for."
    assert O.swear_block(world, me, "abstinence", friend) == "Abstinence is sworn for no one."
    for kind, whom in (("vengeance", foe), ("protection", friend), ("abstinence", None)):
        swear(game, kind, whom)
    assert O.swear_block(world, me, "protection", foe) == "Three oaths already weigh on your heart."


def test_an_oath_sworn_steadies_the_heart_and_is_told(game):
    world, me = game.world, game.player.id
    swear(game, "abstinence")
    [oath] = O.oaths(world, me)
    assert oath["kind"] == "abstinence" and oath["until"] == world.time + O.KINDS["abstinence"]
    assert HT.steady(world, me) == 65.0 and world.facts("oath_sworn", subject=me)


def test_vengeance_is_kept_by_any_hand(game):
    world, me = game.world, game.player.id
    foe = someone(game, "foe")
    D.add_demon(world, me, "grudge", foe, 2)
    swear(game, "vengeance", foe)
    dies(game, foe, someone(game, "stranger"))
    assert O.oaths(world, me) == [] and HT.steady(world, me) == 80.0 and world.facts("oath_kept", subject=me)


def test_a_protected_one_slain_or_an_abstinent_kill_breaks_the_oath(game):
    world, me = game.world, game.player.id
    friend, foe = someone(game, "friend"), someone(game, "foe")
    swear(game, "protection", friend)
    dies(game, friend, someone(game, "killer"))
    assert O.oaths(world, me) == [] and HT.steady(world, me) == 35.0
    assert any(d["kind"] == "guilt" and d["weight"] == 3 for d in D.demons(world, me))
    swear(game, "abstinence")
    dies(game, foe, me)
    assert O.oaths(world, me) == [] and len(world.facts("oath_broken", subject=me)) == 2


def test_the_seasons_settle_oaths_whose_time_ran_out(game):
    world, me = game.world, game.player.id
    foe, friend = someone(game, "foe"), someone(game, "friend")
    D.add_demon(world, me, "grudge", foe, 2)
    swear(game, "vengeance", foe)
    swear(game, "protection", friend)
    world.set_time(world.time + O.KINDS["protection"])
    commit(world, O.season_hook(world, 0))
    assert [o["kind"] for o in O.oaths(world, me)] == ["vengeance"] and HT.lean(world, me) == 10.0
    world.set_time(world.time + O.KINDS["vengeance"])
    commit(world, O.season_hook(world, 0))
    assert O.oaths(world, me) == [] and world.facts("oath_broken", subject=me)


def test_a_broken_oath_is_dishonour():
    assert reputation.PATH_VALUE["oath_broken"] < 0 < reputation.PATH_VALUE["oath_kept"]


def test_check_heart_flags_a_malformed_oath(game):
    world, me = game.world, game.player.id
    swear(game, "abstinence")
    assert check_heart(world) == []
    HT.write(world, me, oaths=[{"kind": "silence", "whom": None, "until": 0, "sworn_at": 0}] * 4)
    assert "oath" in " | ".join(check_heart(world))
