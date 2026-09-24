"""Phase 4c final review: the fixes, each pinned by a test that failed first."""
import random

import pytest

import systems.agendas as agendas
import systems.duel as duel
import systems.encounters as encounters
import systems.lives as lives
import systems.market as market
import systems.price_events as price_events
from debug.invariants import check_lineage, check_trade
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.creation import CreationChoice
from systems.goods import GOODS, capacity, pack_weight
from systems.purse import silver_of
from world.gen.materialize import region_of


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


def robber(game, **data):
    return founding.make_person(game.world, "test:robber", game.place.id,
                                **{"occupation": "hunter", "age": 30, "traits": ["greedy", "kind"], **data})


def lose(game, npc):
    game._start_duel(npc, "duel")
    d = game.combat
    event = duel._end_event(game.world, d, "lost", "broken", random.Random(1), d.harm, 3)
    lines = game._commit([event])
    return lines + game._finish_duel(event.data)


@pytest.mark.parametrize("level", [0.2, 0.6, 1.0])
@pytest.mark.parametrize("guild", [False, True])
def test_a_round_trip_never_gains_silver(game, monkeypatch, level, guild):
    monkeypatch.setattr(market, "_guild_here", lambda world, town: guild)
    me, town = game.player.id, game.place.id
    game.world.update_data(me, silver=100000, goods={})
    game.world.update_data(town, market={"jade": [level, market.day(game.world)]})
    start = silver_of(game.world, me)
    for _ in range(10):
        for n in (1, 5, 10):
            game.perform(Action("buy_goods", ("jade", n)))
            game.perform(Action("sell_goods", ("jade", n)))
            game.perform(Action("sell_goods", ("jade", n)))
            game.perform(Action("buy_goods", ("jade", n)))
    assert silver_of(game.world, me) <= start


def test_losing_the_mule_never_leaves_an_overfull_pack(game, monkeypatch):
    monkeypatch.setattr(market, "MULE_THEFT", 1.0)
    me = game.player.id
    game.world.update_data(me, silver=50, mule=True, goods={})
    room = capacity(game.world, me)
    iron = (room - pack_weight({"rice": 1, "salt": 1, "wine": 1, "tea": 1})) // GOODS["iron"][1]
    game.world.update_data(me, goods={"iron": iron, "rice": 1, "salt": 1, "wine": 1, "tea": 1})
    assert pack_weight(game.player.data["goods"]) <= room
    lose(game, robber(game))
    assert not game.player.data.get("mule")
    assert pack_weight(game.player.data["goods"]) <= capacity(game.world, me)
    assert check_trade(game.world) == []


def test_a_penniless_trader_is_still_robbed_of_goods(game):
    game.world.update_data(game.player.id, silver=0, goods={"silk": 4})
    lose(game, robber(game))
    assert game.player.data["goods"] == {"silk": 2}


def test_a_kind_victor_takes_no_goods(game):
    game.world.update_data(game.player.id, silver=0, goods={"silk": 4})
    lose(game, robber(game, traits=["kind", "honest"]))
    assert game.player.data["goods"] == {"silk": 4}


def test_catching_up_does_not_start_old_famines_now(game, monkeypatch):
    monkeypatch.setattr(price_events, "FAMINE_CHANCE", 1.0)
    world = game.world
    now = lives.current_season(world)
    events = price_events.season_events(world, now - 10)
    assert all(e.data["until"] <= world.time for e in events if e.kind == "price_shift") or not events
    world_facts = len(world.facts(predicate="shortage"))
    from world.events import commit
    commit(world, events)
    assert len(world.facts(predicate="shortage")) == world_facts
    assert price_events.live(world) == []


def test_expired_price_events_are_cleared_away(game):
    world = game.world
    price_events.shift(world, "town", game.place.id, {"iron": 2.0}, world.time + 1, "test", news=False)
    world.set_time(world.time + 10)
    price_events.season_events(world, lives.current_season(world))
    assert world.entities("price_event") == []


def test_a_rumour_leaves_the_other_visit_prices_their_age(game):
    me, town = game.player.id, game.place.id
    market.record_visit(game.world, me, town)
    seen = game.world.time
    game.world.set_time(game.world.time + 400)
    price_events.shift(game.world, "town", town, {"iron": 3.0}, game.world.time + 360, "test")
    [fact] = game.world.facts(predicate="shortage", subject=town)
    from systems.beliefs import believe
    believe(game.world, me, fact.id, fact.variant, None, 0.8, 2, "test")
    book = market.known_prices(game.world, me)[town]
    assert book["iron"] == (fact.data["price"], fact.time, "rumour")
    assert book["rice"][1:] == (seen, "visit")


def test_small_trades_stay_out_of_the_journal(game):
    me = game.player.id
    game.world.update_data(me, silver=10000)
    game.perform(Action("buy_goods", ("jade", 5)))
    for _ in range(80):
        game.perform(Action("buy_goods", ("rice", 1)))
        game.perform(Action("sell_goods", ("rice", 1)))
    journal = [t for t, _ in game.perform(Action("journal")).lines]
    assert any("jade" in t for t in journal)
    assert not any("rice" in t for t in journal)


def test_the_heir_takes_up_the_pack_and_the_mule(game, monkeypatch):
    world, old = game.world, game.player.id
    son = founding.make_person(world, "test:son", game.place.id, occupation="herbalist", age=20)
    agendas._pair(world, old, son, "child")
    world.update_data(old, goods={"jade": 3, "silk": 2}, mule=True)
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 1.0)
    game.perform(Action("meditate", 90))
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    game.perform(Action("succeed", son))
    heir = world.entity(son).data
    assert heir["goods"] == {"jade": 3, "silk": 2} and heir.get("mule")
    assert not world.entity(old).data.get("goods") and not world.entity(old).data.get("mule")
    assert check_lineage(world) == [] and check_trade(world) == []


def test_an_heir_carries_only_what_they_can(game, monkeypatch):
    world, old = game.world, game.player.id
    son = founding.make_person(world, "test:son", game.place.id, occupation="herbalist", age=20)
    agendas._pair(world, old, son, "child")
    world.update_data(old, goods={"iron": 200, "jade": 2})
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 1.0)
    game.perform(Action("meditate", 90))
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    game.perform(Action("succeed", son))
    heir = world.entity(son).data
    assert heir["goods"]["jade"] == 2 and pack_weight(heir["goods"]) <= capacity(world, son)
    assert not world.entity(old).data.get("goods")
    assert check_lineage(world) == [] and check_trade(world) == []


def test_the_lineage_rule_catches_goods_left_on_an_ancestor(game, monkeypatch):
    world, old = game.world, game.player.id
    son = founding.make_person(world, "test:son", game.place.id, occupation="herbalist", age=20)
    agendas._pair(world, old, son, "child")
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 1.0)
    game.perform(Action("meditate", 90))
    monkeypatch.setattr(lives, "death_chance", lambda age, realm: 0.0)
    game.perform(Action("succeed", son))
    world.update_data(old, goods={"rice": 1})
    assert any("ancestor" in p for p in check_lineage(world))
