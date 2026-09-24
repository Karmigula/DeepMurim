import pytest

import systems.encounters as encounters
import systems.lives as lives
import systems.market as market
import systems.price_events as price_events
import systems.world_clock as clock
from engine.game import Game
from narrate.gossip_text import rumour_text
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from world.events import Event, commit
from world.gen.materialize import ensure_town, region_of
from world.gen.region import region_spec


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
    monkeypatch.setattr(market, "drift", lambda world, town, good: 1.0)
    monkeypatch.setattr(price_events, "FAMINE_CHANCE", 0.0)
    monkeypatch.setattr(price_events, "HARVEST_CHANCE", 0.0)


def base(game, town, good):
    """The price with no events: every hook but the price events."""
    return market.price(game.world, town, good) / market.event_factor(game.world, town, good)


def test_a_clash_makes_iron_dear_there_and_nearby(game):
    town = game.place.id
    other = ensure_town(game.world, *[region_of(game.world, town).data[k] for k in ("x", "y")], 1) \
        if region_spec(game.world.world_seed, *[region_of(game.world, town).data[k] for k in ("x", "y")]).town_count > 1 else None
    a, b = F.ensure_roster(game.world)[:2]
    commit(game.world, [Event("clash", (a, b), town, {"season": 0, "hall_lost": False, "abstract": False})])
    assert market.event_factor(game.world, town, "iron") == pytest.approx(1.8 * 1.3)
    assert market.event_factor(game.world, town, "herbs") == pytest.approx(1.5)
    if other is not None:
        assert market.event_factor(game.world, other, "iron") == pytest.approx(1.3)
    [fact] = [f for f in game.world.facts(predicate="shortage", subject=town) if f.data["good"] == "iron"]
    assert fact.data["price"] == market.price(game.world, town, "iron")
    assert rumour_text(game.world, fact.variant, game.player.id) == f"Iron is dear in {game.world.entity(town).name}."
    game.world.set_time(game.world.time + lives.SEASON + 1)
    assert market.event_factor(game.world, town, "iron") == 1.0


def test_a_famine_empties_the_rice_barrels(game, monkeypatch):
    monkeypatch.setattr(price_events, "FAMINE_CHANCE", 1.0)
    town = game.place.id
    clock.world_tick(game.world)
    game.world.set_time(game.world.time + lives.SEASON)
    clock.run_due(game.world)
    assert market.event_factor(game.world, town, "rice") >= 3.0
    assert market.event_factor(game.world, town, "salt") >= 1.5


def test_a_bumper_harvest_makes_local_goods_cheap(game, monkeypatch):
    monkeypatch.setattr(price_events, "HARVEST_CHANCE", 1.0)
    from systems.goods import region_goods
    town = game.place.id
    made, _ = region_goods(game.world, region_of(game.world, town))
    clock.world_tick(game.world)
    game.world.set_time(game.world.time + lives.SEASON)
    clock.run_due(game.world)
    assert all(market.event_factor(game.world, town, g) == pytest.approx(0.6) for g in made)
    assert any(f.data["good"] in made for f in game.world.facts(predicate="glut"))


def a_city(game):
    for x in range(-4, 5):
        for y in range(-4, 5):
            for i in range(region_spec(game.world.world_seed, x, y).town_count):
                town = ensure_town(game.world, x, y, i)
                if game.world.entity(town).data["kind"] == "city":
                    return town
    raise AssertionError("no city")


def test_cities_feast_in_spring(game):
    city = a_city(game)
    assert price_events.factor(game.world, city, "wine") == pytest.approx(1.4)  # the game begins in spring
    game.world.set_time(game.world.time + lives.SEASON)
    assert price_events.factor(game.world, city, "wine") == 1.0


def test_a_weak_faction_arms_itself(game):
    sect = next(f for f in F.ensure_roster(game.world) if game.world.entity(f).data["type"] == "orthodox_sect")
    seat = halls.seat_of(game.world, sect)
    game.world.update_data(sect, power=90)
    strong = price_events.factor(game.world, seat, "iron")
    game.world.update_data(sect, power=20)
    assert price_events.factor(game.world, seat, "iron") == pytest.approx(strong * 1.2)


def test_price_events_stack_but_are_clamped(game):
    town = game.place.id
    until = game.world.time + lives.SEASON
    for _ in range(3):
        price_events.shift(game.world, "town", town, {"rice": 3.0}, until, "test")
    assert market.event_factor(game.world, town, "rice") == market.EVENT_MAX
    for _ in range(3):
        price_events.shift(game.world, "town", town, {"tea": 0.2}, until, "test")
    assert market.event_factor(game.world, town, "tea") == market.EVENT_MIN


def test_flooding_a_market_starts_a_rumour(game):
    town, me = game.place.id, game.player.id
    game.world.update_data(me, goods={"rice": 40})
    game._commit(market.sell_events(game.world, me, town, "rice", 30))
    [fact] = game.world.facts(predicate="glut", subject=town)
    assert fact.data["good"] == "rice"
    assert rumour_text(game.world, fact.variant, me) == f"Rice is going cheap in {game.world.entity(town).name}."
