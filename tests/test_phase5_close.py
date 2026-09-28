"""The close of phase 5 (phase 5f spec 8): 5c's absent masters and 5d's commission lost with a smith."""

import pytest

import systems.control as C
import systems.craft_world as CW
import systems.encounters as encounters
import systems.travel as travel
from engine.game import Game
from systems import founding
from systems.creation import CreationChoice
from systems.purse import silver_of
from world.events import Event, commit
from world.gen.materialize import ensure_town


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.update_data(g.player.id, silver=5000)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def test_a_master_in_another_town_does_not_feed_their_bound(game, monkeypatch):
    world, here = game.world, game.place.id
    monkeypatch.setattr(C, "CURE_SEEK", 0.0)
    elsewhere = ensure_town(world, *travel.routes_from(world, game.place)[0].dest)
    master = founding.make_person(world, "test:close:master", here, occupation="monk", age=50, realm="first-rate")
    near, far = (founding.make_person(world, f"test:close:{t}", here, occupation="tea seller", age=30)
                 for t in ("near", "far"))
    for bound in (near, far):
        C.bind(world, bound, master)
    world.unrelate(far, "located_in")
    world.relate(far, elsewhere, "located_in")
    assert C.fed(world, master, near) and not C.fed(world, master, far)
    before = C.bound(world, far)["fed_until"]
    world.set_time(world.time + 4 * C.MONTH)
    commit(world, C.season_hook(world, 1))
    assert C.bound(world, near)["fed_until"] > world.time and C.bound(world, far)["fed_until"] == before
    assert C.days_starved(world, far) > 0


def test_a_smiths_estate_returns_a_commission_unforged(game):
    world, me, here = game.world, game.player.id, game.place.id
    smith = founding.make_person(world, "test:close:smith", here, occupation="blacksmith", age=50)
    world.update_data(smith, craft_skill=3)
    commit(world, CW.commission_forge_events(world, me, smith, "weapon", "sword", here))
    paid = 5000 - silver_of(world, me)
    assert paid > 0 and CW.pending(world, me)[0]["price"] == paid
    commit(world, [Event("died", (smith, smith), here, {"cause": "illness", "world": True})])
    assert silver_of(world, me) == 5000 and CW.pending(world, me) == []
    assert any(e.kind == "commission_refunded" for e in world.chronicle_about(me, limit=5))


def test_an_older_commission_without_a_price_is_returned_at_the_stall_price(game):
    world, me, here = game.world, game.player.id, game.place.id
    smith = founding.make_person(world, "test:close:old", here, occupation="blacksmith", age=50)
    world.update_data(me, commissions=[{"smith": smith, "slot": "weapon", "form": "saber", "grade": 1,
                                        "ready_at": world.time + 40}])
    commit(world, [Event("died", (smith, smith), here, {"cause": "illness", "world": True})])
    assert silver_of(world, me) > 5000 and CW.pending(world, me) == []
