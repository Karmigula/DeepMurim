import pytest

import systems.encounters as encounters
import systems.goods as goods
import systems.market as market
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
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


@pytest.fixture
def still(monkeypatch):
    monkeypatch.setattr(market, "drift", lambda world, town, good: 1.0)


def rich(game, silver=5000):
    game.world.update_data(game.player.id, silver=silver)


def test_each_region_produces_two_goods_and_lacks_two(game):
    region = region_of(game.world, game.place.id)
    made, lacking = goods.region_goods(game.world, region)
    assert len(made) == len(lacking) == 2 and not set(made) & set(lacking)
    assert goods.region_goods(game.world, region) == (made, lacking)


def test_the_price_is_the_product_of_its_factors(game, still):
    town = game.place.id
    kind = game.world.entity(town).data["kind"]
    made, lacking = goods.region_goods(game.world, region_of(game.world, town))
    for good, (base, _, category) in goods.GOODS.items():
        region = goods.PRODUCED if good in made else goods.LACKED if good in lacking else 1.0
        kind_factor = 1.2 if kind == "city" and category == "luxury" else 0.9 if kind == "village" and category == "staple" else 1.0
        assert market.price(game.world, town, good) == max(1, round(base * region * kind_factor))


def test_buying_raises_the_price_and_the_market_recovers(game, still):
    rich(game)
    town, me = game.place.id, game.player.id
    before = market.price(game.world, town, "jade")
    game._commit(market.buy_events(game.world, me, town, "jade", 10))
    assert goods.carried(game.world, me) == {"jade": 10}
    assert market.stock(game.world, town, "jade") == pytest.approx(0.9)
    assert market.price(game.world, town, "jade") > before
    game.world.set_time(game.world.time + 4 * 30)
    assert market.stock(game.world, town, "jade") == pytest.approx(1 - 0.1 * 0.9 ** 30, abs=1e-6)


def test_selling_pays_less_than_buying(game, still):
    rich(game)
    town, me = game.place.id, game.player.id
    game._commit(market.buy_events(game.world, me, town, "silk", 5))
    silver = silver_of(game.world, me)
    unit = market.sell_price(game.world, town, "silk", 5)
    game._commit(market.sell_events(game.world, me, town, "silk", 5))
    assert silver_of(game.world, me) == silver + 5 * unit
    assert unit < market.price(game.world, town, "silk") or unit == 1


def test_buying_is_refused_with_a_reason(game, still):
    town, me = game.place.id, game.player.id
    game.world.update_data(me, silver=0)
    assert market.buy_block(game.world, me, town, "rice", 1) == "You cannot afford that."
    rich(game)
    too_many = goods.capacity(game.world, me) // goods.GOODS["iron"][1] + 1
    assert market.buy_block(game.world, me, town, "iron", too_many) == "Your pack cannot hold that much."
    assert market.sell_block(game.world, me, town, "tea", 1) == "You have no tea to sell."


def test_a_market_can_be_flooded_but_never_below_one(game, still):
    rich(game, 10 ** 7)
    town, me = game.place.id, game.player.id
    game.world.update_data(me, goods={"rice": 400})
    for _ in range(4):
        game._commit(market.sell_events(game.world, me, town, "rice", 100))
    assert market.stock(game.world, town, "rice") == market.STOCK_MAX
    assert market.price(game.world, town, "rice") >= 1 and market.sell_price(game.world, town, "rice") >= 1
    game.world.update_data(me, goods={})
    while market.buy_block(game.world, me, town, "salt", 10) is None:
        game._commit(market.buy_events(game.world, me, town, "salt", 10))
        game.world.update_data(me, goods={})
    assert market.stock(game.world, town, "salt") >= market.STOCK_MIN


def test_a_mule_carries_more(game):
    me = game.player.id
    base = goods.capacity(game.world, me)
    game.world.update_data(me, silver=100)
    game._commit(market.mule_events(game.world, me, game.place.id))
    assert goods.capacity(game.world, me) == base + goods.MULE_CAPACITY and silver_of(game.world, me) == 40
    assert market.mule_block(game.world, me) == "You already have a mule."


def test_the_merchant_guild_pays_more(game, still):
    town = game.place.id
    guild = next(f for f in F.ensure_roster(game.world) if game.world.entity(f).data["type"] == "merchant_guild")
    plain = market.sell_price(game.world, town, "jade")
    game.world.update_data(town, halls=[*halls.halls_here(game.world, town), guild])
    assert market.sell_price(game.world, town, "jade") >= plain
    assert market.sell_price(game.world, town, "jade") == int(market.price(game.world, town, "jade") * market.GUILD_CUT)


def test_the_same_seed_gives_the_same_prices(game, tmp_path):
    twin = Game.new(tmp_path / "twin.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    twin.start()
    assert market.prices(game.world, game.place.id) == market.prices(twin.world, twin.place.id)
    twin.close()


def test_a_visit_writes_the_price_book(game):
    market.record_visit(game.world, game.player.id, game.place.id)
    entry = game.player.data["price_book"][str(game.place.id)]
    assert entry["source"] == "visit" and entry["prices"] == market.prices(game.world, game.place.id)
