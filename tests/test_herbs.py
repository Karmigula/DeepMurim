import pytest

import systems.herbs as H
from engine.game import Game
from systems.bodies import load_body
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.events import commit
from world.gen.materialize import region_of


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def test_every_herb_is_well_made_and_grows_somewhere():
    for name, h in H.HERBS.items():
        assert h["element"] in ("fire", "water", "wood", "metal", "earth", "poison", "none"), name
        assert h["polarity"] in ("yin", "yang", "balanced") and 1 <= h["potency"] <= 5 and 0 <= h["toxicity"] <= 5
        assert h["terrains"] and h["price"] > 0
    assert len(H.HERBS) >= 24
    for terrain in ("plains", "mountains", "river", "forest", "marsh", "hills"):
        assert H.growing(terrain), terrain


def test_tasting_teaches_a_herb_and_a_toxic_one_poisons(game):
    world, me = game.world, game.player.id
    mild = H.make_herb(world, "willow bark", 0, me)
    assert not H.known(world, me, "willow bark") and H.taste_block(world, me, mild) is None
    commit(world, H.taste_events(world, me, mild, game.place.id))
    assert H.known(world, me, "willow bark") and mild not in world.targets(me, "owns")
    assert load_body(world, me).poisons == []
    black = H.make_herb(world, "black lotus", 0, me)
    commit(world, H.taste_events(world, me, black, game.place.id))
    [p] = load_body(world, me).poisons
    assert p["grade"] == 5 and p["strength"] == 10


def test_gathering_finds_the_herbs_of_the_land(game):
    world, me, town = game.world, game.player.id, game.place.id
    terrain = region_of(world, town).data["terrain"]
    found, guarded, start = [], 0, world.time
    for _ in range(12):
        [event] = H.gather_events(world, me, town)
        commit(world, [event])
        found += event.data["found"]
        guarded += event.data["guarded"]
    assert found and all(f["herb"] in H.growing(terrain) for f in found)
    assert world.time == start + 12 * H.GATHER_WATCHES
    assert len(H.herbs_of(world, me)) == len(found)


def test_the_herbalist_sells_by_the_season_dearer_for_what_does_not_grow_here(game):
    world, me, town = game.world, game.player.id, game.place.id
    offers = H.stock(world, town)
    assert H.STOCK[0] <= len(offers) <= H.STOCK[1]
    terrain = region_of(world, town).data["terrain"]
    local = next(n for n in H.HERBS if terrain in H.HERBS[n]["terrains"])
    other = next(n for n in H.HERBS if terrain not in H.HERBS[n]["terrains"])
    assert H.price(world, town, other, 0) >= round(H.props(other)["price"] * H.LACKED * 0.9)
    assert H.price(world, town, local, 0) <= round(H.props(local)["price"] * 1.1) + 1
    world.update_data(me, silver=1000)
    offer = offers[0]
    commit(world, H.buy_events(world, me, town, offer["key"]))
    assert [h.data["herb"] for h in H.herbs_of(world, me)] == [offer["herb"]]
    assert offer["key"] not in {o["key"] for o in H.stock(world, town)}


def test_a_furnace_is_bought_once(game):
    world, me, town = game.world, game.player.id, game.place.id
    world.update_data(me, silver=H.FURNACE_PRICE)
    assert H.furnace_block(world, me) is None
    commit(world, H.furnace_events(world, me, town))
    assert H.furnace_of(world, me) is not None and silver_of(world, me) == 0
    assert H.furnace_block(world, me) == "You have a furnace already."


def test_a_treasure_race_herb_is_a_herb_of_the_table():
    assert H.prize_herb("a thousand-year ginseng") == ("ginseng", 3)
    assert H.prize_herb("a blood lotus") == ("blood lotus", 2)


def test_a_won_herb_is_a_herb_of_the_table(game):
    from systems.races import make_prize
    world, me = game.world, game.player.id
    item = make_prize(world, me, {"kind": "herb", "name": "a thousand-year ginseng", "value": 300}, 1)
    assert world.entity(item).kind == "treasure"  # still 4d's treasure, sold as one
    assert H.herb_info(world.entity(item)) == ("ginseng", 3) and world.entity(item) in H.herbs_of(world, me)
