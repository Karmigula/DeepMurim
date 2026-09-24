import pytest

import systems.encounters as encounters
import systems.market as market
from debug.invariants import check_trade
from engine.actions import Action
from engine.game import Game
from systems.creation import CreationChoice
from systems.price_events import shift


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


def test_honest_trading_breaks_no_rule(game):
    game.world.update_data(game.player.id, silver=500)
    game.perform(Action("market"))
    game.perform(Action("trade_good", "silk"))
    game.perform(Action("buy_goods", ("silk", 5)))
    shift(game.world, "town", game.place.id, {"iron": 2.0}, game.world.time + 360, "test")
    assert check_trade(game.world) == []


def test_bad_goods_and_an_overfull_pack_are_caught(game):
    game.world.update_data(game.player.id, goods={"rice": -1})
    assert any("goods" in p for p in check_trade(game.world))
    game.world.update_data(game.player.id, goods={"iron": 999})
    assert any("pack" in p for p in check_trade(game.world))


def test_wild_stock_and_multipliers_are_caught(game):
    game.world.update_data(game.place.id, market={"rice": [9.0, 0]})
    assert any("stock" in p for p in check_trade(game.world))
    game.world.update_data(game.place.id, market={})
    shift(game.world, "town", game.place.id, {"rice": 9.0}, game.world.time + 360, "test")
    assert any("multiplier" in p for p in check_trade(game.world))


def test_a_name_inside_another_is_not_a_mention():
    from debug.invariants import mentions
    assert mentions("wang clan", "ha rinhwa the clan head (wang clan) (36)")
    assert not mentions("wang clan", "ha rinhwa the clan head (hwang clan) (36)")


def test_a_price_book_from_the_future_is_caught(game):
    market.record_visit(game.world, game.player.id, game.place.id)
    book = game.player.data["price_book"]
    book[str(game.place.id)]["time"] = game.world.time + 100
    game.world.update_data(game.player.id, price_book=book)
    assert any("price book" in p for p in check_trade(game.world))
