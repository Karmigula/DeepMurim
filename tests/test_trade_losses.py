import random

import pytest

import systems.duel as duel
import systems.encounters as encounters
import systems.market as market
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.creation import CreationChoice
from systems.goods import GOODS


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


def robber(game):
    return founding.make_person(game.world, "test:robber", game.place.id, occupation="hunter", age=30,
                                traits=["greedy", "kind"])


def lose(game, npc):
    game._start_duel(npc, "duel")
    d = game.combat
    event = duel._end_event(game.world, d, "lost", "broken", random.Random(1), d.harm, 3)
    lines = game._commit([event])
    return lines + game._finish_duel(event.data)


def test_a_robber_takes_half_the_goods_and_maybe_the_mule(game, monkeypatch):
    monkeypatch.setattr(market, "MULE_THEFT", 1.0)
    me = game.player.id
    game.world.update_data(me, silver=50, goods={"silk": 5, "jade": 2}, mule=True)
    npc = robber(game)
    lines = lose(game, npc)
    assert game.player.data["goods"] == {"silk": 3, "jade": 1} and not game.player.data.get("mule")
    assert game.world.entity(npc).data["goods"] == {"silk": 2, "jade": 1}
    journal = [t for t, _ in game.perform(Action("journal")).lines]
    assert any("mule" in t for t in journal) and lines


def test_a_robbery_of_nothing_takes_nothing(game):
    game.world.update_data(game.player.id, silver=50, goods={"rice": 1})
    lose(game, robber(game))
    assert game.player.data["goods"] == {"rice": 1}
    assert not [e for e in game.world.chronicle_about(game.player.id, limit=20) if e.kind == "lost_goods"]


def bandit_on_the_road(game, toll):
    bandit = founding.make_person(game.world, "test:bandit", game.place.id, occupation="bandit", age=30)
    events = encounters.encounter_events(game.player.id, bandit, game.place.id, "bandit", toll)
    game._commit(events)
    game.encounter = encounters.encounter_state(events[-1])
    return bandit


def test_a_toll_can_be_paid_in_goods(game):
    me = game.player.id
    game.world.update_data(me, silver=0, goods={"jade": 3, "rice": 5})
    bandit = bandit_on_the_road(game, 60)
    turn = game.perform(Action("look"))
    assert Action("road", "pay_goods") in [c.action for c in turn.choices]
    game.perform(Action("road", "pay_goods"))
    taken = game.world.entity(bandit).data["goods"]
    worth = sum(market.sell_price(game.world, game.place.id, g) * n for g, n in taken.items())
    assert worth >= 60 and "jade" in taken and game.encounter is None


def test_no_goods_toll_when_the_pack_is_too_poor(game):
    game.world.update_data(game.player.id, silver=0, goods={"rice": 1})
    bandit_on_the_road(game, 500)
    assert Action("road", "pay_goods") not in [c.action for c in game.perform(Action("look")).choices]


def test_toll_goods_prefer_value_per_weight(game):
    game.world.update_data(game.player.id, goods={"jade": 1, "iron": 10})
    goods = market.toll_goods(game.world, game.player.id, game.place.id, 20)
    assert goods and next(iter(goods)) == max(goods, key=lambda g: GOODS[g][0] / GOODS[g][1])
