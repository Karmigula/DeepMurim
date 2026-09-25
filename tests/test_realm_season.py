import time
from pathlib import Path

import pytest

import systems.encounters as encounters
import systems.realm_gates as G
import systems.secret_realms as SR
import systems.sky as sky
import systems.world_events as W
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.creation import CreationChoice
from world.events import commit
from world.gen.materialize import ensure_town


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.set_time(10 * W.SEASON + 8)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def room(kind, **contents):
    return {"kind": kind, "state": "untouched", "contents": contents}


def opening_with(game, bands, floors=None):
    world, town = game.world, game.place.id
    realm = SR.ensure_realms(world)[0]
    changes = {"gate": town, "rule": {"kind": "open", "value": None}}
    if floors:
        changes["floors"] = floors
    world.update_data(realm, **changes)
    teams = [{"faction": None, "members": list(b)} for b in bands]
    data = {**SR.opening_data(realm), "delvers": [p for b in bands for p in b], "teams": teams}
    commit(world, sky.start_events(world, "realm_opening", town, world.time, data))
    occurrence = W.index(world)[-1][W.ID]
    world.set_time(world.entity(occurrence).data["active"][0])
    return realm, occurrence


def people(world, town, count, prefix):
    return [founding.make_person(world, f"test:{prefix}:{i}", town, occupation="wandering swordsman", age=25,
                                 realm="second-rate") for i in range(count)]


def test_a_delve_step_with_three_bands_inside_is_quick(game):
    world, town = game.world, game.place.id
    floors = [[room("trial", trial="formation"), room("treasure", prize={"kind": "herb", "name": "a herb", "value": 9}),
               room("guardian", species="stone lion", realm=2, guardian=None), room("stair")],
              [room("trial", trial="pressure"), room("stair")], [room("inheritance")]]
    bands = [people(world, town, 3, f"band{i}") for i in range(3)]
    realm, _ = opening_with(game, bands, floors)
    game.perform(Action("look"))
    game.perform(Action("enter_realm", realm))
    game.perform(Action("delve_rest"))
    start = time.process_time()
    game.perform(Action("delve_rest"))
    elapsed = time.process_time() - start
    assert elapsed < 0.04, f"a step took {elapsed * 1000:.0f} ms"


def test_a_closing_far_away_with_twelve_delvers_is_quick(game):
    world, town = game.world, game.place.id
    realm, occurrence = opening_with(game, [people(world, town, 3, f"sect{i}") for i in range(4)])
    world.unrelate(game.player.id, "located_in")
    world.relate(game.player.id, ensure_town(world, 5, 5, 0), "located_in")
    world.set_time(world.entity(occurrence).data["active"][1])
    start = time.process_time()
    commit(world, G.closing_events(world, world.entity(occurrence)))
    elapsed = time.process_time() - start
    assert world.entity(occurrence).data["data"]["closed"]
    assert elapsed < 0.01 + 0.0157, f"a closing took {elapsed * 1000:.0f} ms"  # 10 ms, and one tick of the CPU clock


def test_a_young_dragon_is_judged_by_the_age_believed_when_listed(game):
    import systems.rankings as R
    from debug.invariants import check_rankings
    from tests.test_rankings import deed, master, publish
    world, town = game.world, game.place.id
    youth = master(world, town, "test:youth", realm="second-rate", age=30)
    deed(world, youth, "tribulation", town, realm="second-rate", age=30)
    assert youth in publish(world)["lists"]["young"]
    world.set_time(world.time + R.YEAR)  # a year on, the Pavilion would think them 31; the list is last spring's
    world._rankings_checked = None
    assert check_rankings(world) == []


def test_the_fork_guide_covers_secret_realms():
    guide = Path("docs/world-events.md").read_text(encoding="utf-8")
    for word in ("secret_realm", "realm_opening", "realm_awakening", "PLACES", "GUARDIANS", "TRIALS", "RULES_ANCIENT",
                 "CHAMBER_WEIGHTS", "check_realms", "sealed_in", "realm_spirit", "delve_at"):
        assert word in guide, word
