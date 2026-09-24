"""Phase 4c deferred minors, each pinned by a test that failed first."""
import subprocess
import sys

import pytest

import systems.encounters as encounters
import systems.price_events as price_events
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.creation import CreationChoice
from world.seed import rng_for


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


def test_famines_follow_the_region_not_the_order_it_was_found(game, monkeypatch):
    monkeypatch.setattr(price_events, "FAMINE_CHANCE", 0.5)
    monkeypatch.setattr(price_events, "HARVEST_CHANCE", 0.0)
    world = game.world
    n = world.time // 360
    hit = {e.data["place"] for e in price_events.season_events(world, n) if e.data["cause"] == "famine"}
    expected = {r.id for r in world.entities("region")
                if rng_for(world.world_seed, f"famine:{r.seed_path}:{n}").random() < 0.5}
    assert hit == expected


def test_the_mule_is_bought_at_the_market(game):
    game.world.update_data(game.player.id, silver=100)
    assert Action("buy_mule") not in [c.action for c in game.perform(Action("look")).all_choices]
    assert Action("buy_mule") in [c.action for c in game.perform(Action("market")).all_choices]


def test_prices_react_to_events_without_the_narrator_loaded():
    code = "import systems.market as m, systems.world_clock as c; print(len(m.EVENT_FACTORS), len(c.SEASON_HOOKS))"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.split()
    assert int(out[0]) >= 1 and int(out[1]) >= 1


def test_a_toll_in_goods_is_only_for_the_short_of_silver(game):
    me = game.player.id
    game.world.update_data(me, silver=500, goods={"jade": 3})
    bandit = founding.make_person(game.world, "test:bandit", game.place.id, occupation="bandit", age=30)
    events = encounters.encounter_events(me, bandit, game.place.id, "bandit", 60)
    game._commit(events)
    game.encounter = encounters.encounter_state(events[-1])
    game.perform(Action("road", "pay_goods"))
    assert game.player.data["goods"] == {"jade": 3}


def test_the_days_selling_tally_forgets_other_days(game):
    me, town = game.player.id, game.place.id
    game.world.update_data(me, goods={"rice": 5, "salt": 5})
    game.perform(Action("sell_goods", ("rice", 1)))
    game.world.set_time(game.world.time + 8)
    game.perform(Action("sell_goods", ("salt", 1)))
    assert list(game.player.data["sold_today"]) == [f"{town}:salt"]
