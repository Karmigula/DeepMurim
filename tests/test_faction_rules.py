import time

import pytest

from debug.invariants import check_factions, check_people, check_world
from engine.actions import Action, Turn
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from world.gen.materialize import ensure_town
from world.gen.region import region_spec


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def test_a_clean_world_breaks_no_faction_rule(game):
    assert check_factions(game.world) == []


def test_two_open_martial_memberships_are_caught(game):
    ids = [i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] in ("orthodox_sect", "demonic_cult")]
    for fid in ids[:2]:
        game.world.relate(game.player.id, fid, "member_of", 0, {"role": "member", "status": "member", "secret": False, "merit": 0})
    assert any("martial" in p for p in check_factions(game.world))


def test_a_lopsided_stance_is_caught(game):
    a, b = F.ensure_roster(game.world)[:2]
    game.world.relate(a, b, "stance", 0.9)
    assert any("stance" in p for p in check_factions(game.world))


def test_naming_an_unheard_of_faction_is_caught(game):
    far = next(i for i in F.ensure_roster(game.world)
               if i not in halls.halls_here(game.world, game.place.id) and game.world.entity(i).data["type"] == "demonic_cult")
    turn = Turn([(f"The {game.world.entity(far).name} sends its regards.", "npc")], [], {}, "")
    assert any("faction" in p for p in check_people(game, turn))


def test_a_world_full_of_factions_stays_quick(game):
    for x in range(-2, 3):
        for y in range(-2, 3):
            for i in range(region_spec(game.world.world_seed, x, y).town_count):
                halls.settle_town(game.world, ensure_town(game.world, x, y, i))
    assert len(game.world.entities("faction")) >= 12
    check_world(game.world)
    start = time.perf_counter()
    turn = game.perform(Action("look"))
    check_world(game.world)
    check_people(game, turn)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.15, f"a turn and its checks took {elapsed * 1000:.0f} ms"
