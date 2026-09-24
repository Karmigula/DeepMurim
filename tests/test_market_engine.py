import time

import pytest

import systems.encounters as encounters
import systems.market as market
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.beliefs import believe
from systems.creation import CreationChoice
from systems.goods import GOODS
from systems.price_events import shift
from world.gen.materialize import ensure_town


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


def texts(turn):
    return [t for t, _ in turn.lines]


def test_the_market_page_lists_every_good_and_records_the_visit(game):
    turn = game.perform(Action("market"))
    lines = texts(turn)
    assert lines[0].startswith("Market of ")
    assert all(any(t.strip().startswith(good) for t in lines) for good in GOODS)
    assert [c.action.verb for c in turn.choices[:-1]] == ["trade_good"] * len(GOODS)
    assert str(game.place.id) in game.player.data["price_book"]


def test_trading_through_the_menus(game):
    game.world.update_data(game.player.id, silver=1000)
    game.perform(Action("market"))
    turn = game.perform(Action("trade_good", "silk"))
    assert Action("buy_goods", ("silk", 5)) in [c.action for c in turn.choices]
    game.perform(Action("buy_goods", ("silk", 5)))
    assert game.player.data["goods"] == {"silk": 5}
    turn = game.perform(Action("sell_goods", ("silk", 1)))
    assert game.player.data["goods"] == {"silk": 4}
    assert Action("sell_goods", ("silk", 1)) in [c.action for c in turn.choices]


def test_refusals_are_explained(game):
    game.world.update_data(game.player.id, silver=0)
    game.perform(Action("market"))
    game.perform(Action("trade_good", "jade"))
    assert texts(game.perform(Action("buy_goods", ("jade", 1))))[-1] == "You cannot afford that."


def test_the_price_book_mixes_visits_and_rumours(game):
    me = game.player.id
    game.perform(Action("market"))
    far = ensure_town(game.world, 5, 5, 0)
    shift(game.world, "town", far, {"iron": 3.0}, game.world.time + 360, "test")
    [fact] = [f for f in game.world.facts(predicate="shortage", subject=far)]
    believe(game.world, me, fact.id, fact.variant, None, 0.8, 2, "test")
    book = market.known_prices(game.world, me)
    assert book[far]["prices"]["iron"] == fact.data["price"] and book[far]["source"] == "rumour"
    lines = texts(game.perform(Action("prices")))
    name = game.world.entity(far).name
    assert any(t.strip().startswith("iron") and name in t and "heard" in t for t in lines)


def test_a_merchant_passes_on_trade_news(game):
    town, me = game.place.id, game.player.id
    shift(game.world, "town", town, {"salt": 2.0}, game.world.time + 360, "test")
    merchant = founding.make_person(game.world, "test:merchant", town, occupation="merchant")
    turn = game.perform(Action("talk", merchant))
    assert Action("ask_trade") in [c.action for c in turn.all_choices]
    game.perform(Action("ask_trade"))
    assert any(b.variant.get("predicate") == "shortage" for b in game.world.beliefs(me))


def test_the_status_line_shows_the_pack(game):
    game.world.update_data(game.player.id, goods={"silk": 3})
    assert "pack 3/" in game.perform(Action("look")).status


def test_a_mule_from_the_town_menu(game):
    game.world.update_data(game.player.id, silver=100)
    turn = game.perform(Action("look"))
    assert Action("buy_mule") in [c.action for c in turn.all_choices]
    game.perform(Action("buy_mule"))
    assert game.player.data["mule"]


def test_the_town_brief_names_its_cheap_and_dear_goods(game):
    game.world.set_time(game.world.time + 1)
    game.perform(Action("look"))
    facts = " ".join(game.last_briefs[-1].facts)
    assert "is cheap" in facts and "is dear" in facts


def test_an_old_save_trades_from_scratch(tmp_path):
    path = tmp_path / "old.world"
    old = Game.new(path, "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    old.start()
    old.world._conn.execute("update entities set data = json_remove(data, '$.goods', '$.price_book', '$.market')")
    old.close()
    game = Game.load(path)
    game.start()
    assert market.known_prices(game.world, game.player.id) == {}
    assert texts(game.perform(Action("market")))[0].startswith("Market of ")
    game.close()


def test_the_market_is_quick(game):
    start = time.perf_counter()
    game.perform(Action("market"))
    elapsed = time.perf_counter() - start
    assert elapsed < 0.03, f"the market took {elapsed * 1000:.0f} ms"
