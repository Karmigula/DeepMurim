import pytest

import systems.encounters as encounters
import systems.karma as K
import systems.threads as TH
import systems.travel as travel
from engine.actions import Action
from engine.game import Game
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.events import Event, commit
from world.gen.materialize import ensure_town


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


def someone(game, tag, town=None, **data):
    base = {"occupation": "tea seller", "traits": ["curious"], "realm": "third-rate", "age": 40,
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:thread:{tag}")
    game.world.relate(pid, town or game.place.id, "located_in")
    return pid


def elsewhere(game):
    return ensure_town(game.world, *travel.routes_from(game.world, game.place)[0].dest)


def kinds(game):
    return sorted((t["kind"], t["weight"]) for t in TH.threads(game.world, game.player.id))


def test_a_verdict_a_healing_a_freeing_and_an_accusation_tie_threads(game):
    world, me, here = game.world, game.player.id, game.place.id
    a, b, c, d = (someone(game, t) for t in "abcd")
    for verdict, foe in (("spare", a), ("cripple", b)):
        TH._from_duel(world, Event("duel_ended", (me, foe), here, {"result": "won", "by": "player",
                                                                  "verdict": verdict}), 0)
    TH._from_healing(world, Event("healed", (me, c), here, {}), 0)
    TH._from_freeing(world, Event("worms_killed", (me, c), here, {}), 0)
    TH._from_accusing(world, Event("false_accusation", (me, d), here, {}), 0)
    assert kinds(game) == [("accused", 2), ("crippled", 2), ("freed", 3), ("healed", 1), ("spared", 2)]
    TH.add_thread(world, me, a, "spared")
    assert ("spared", 3) in kinds(game)


def test_at_most_twelve_threads_the_lightest_going(game):
    world, me = game.world, game.player.id
    TH.add_thread(world, me, 900, "healed")
    for n in range(12):
        TH.add_thread(world, me, 1000 + n, "bereaved")
    assert len(TH.threads(world, me)) == 12 and ("healed", 1) not in kinds(game)


def test_a_killing_ties_the_player_to_the_dead_ones_kin_and_a_death_ends_its_threads(game):
    world, me, here = game.world, game.player.id, game.place.id
    victim, brother = someone(game, "victim"), someone(game, "brother")
    world.relate(victim, brother, "kin_of", data={"role": "sibling"})
    TH.add_thread(world, me, victim, "robbed")
    commit(world, [Event("died", (me, victim), here, {"cause": "killed"})])
    tied = [t["whom"] for t in TH.threads(world, me)]  # 4b brings the dead one's kin into the world
    assert brother in tied and len(tied) == TH.BEREAVED_KIN and set(k for k, _ in kinds(game)) == {"bereaved"}
    commit(world, [Event("died", (brother, brother), here, {"cause": "illness", "world": True})])
    assert brother not in [t["whom"] for t in TH.threads(world, me)] and len(TH.threads(world, me)) == 1


def test_one_who_owes_you_repays_you_on_the_road(game, monkeypatch):
    world, me = game.world, game.player.id
    monkeypatch.setattr(TH, "FATE_CHANCE", 1.0)
    friend = someone(game, "friend", town=elsewhere(game))
    TH.add_thread(world, me, friend, "spared")
    assert TH.fated_events(world, me, world.entity(elsewhere(game)), None) is None  # at their own home: no road
    [event] = TH.fated_events(world, me, game.place, None)
    assert event.kind == "fated_repaid" and event.data["silver"] == TH.REPAY * 2 * 2
    commit(world, [event])
    assert silver_of(world, me) == 1000 + TH.REPAY * 4 and kinds(game) == []


def test_one_you_wronged_stands_in_the_road_and_takes_amends(game, monkeypatch):
    world, me = game.world, game.player.id
    monkeypatch.setattr(TH, "FATE_CHANCE", 1.0)
    victim = someone(game, "victim", town=elsewhere(game))
    TH.add_thread(world, me, victim, "crippled")
    events = TH.fated_events(world, me, game.place, None)
    assert events[-1].kind == "encounter" and events[-1].data == {"kind": "wronged", "toll": 100, "thread": "crippled"}
    commit(world, events)
    game.encounter = encounters.encounter_state(events[-1])
    turn = game._turn([])
    assert "Make amends (100 silver)" in [c.label for c in turn.choices]
    game.perform(Action("road", "pay"))
    assert kinds(game) == [] and K.karma_of(world, me)["merit"] == TH.AMENDS_MERIT and silver_of(world, me) == 900


def test_the_wronged_say_why_they_stand_there(game, monkeypatch):
    world, me = game.world, game.player.id
    monkeypatch.setattr(TH, "FATE_CHANCE", 1.0)
    victim = someone(game, "victim", town=elsewhere(game))
    TH.add_thread(world, me, victim, "robbed")
    lines = game._commit(TH.fated_events(world, me, game.place, None))
    assert any("You took my silver" in t for t, _ in lines)
