import json
import time
from pathlib import Path

import pytest

import systems.encounters as encounters
import systems.sky as sky
import systems.tournaments as T
import systems.world_events as W
from debug.invariants import check_tournaments
from engine.game import Game
from engine.tournament_page import bracket_lines
from systems.creation import CreationChoice
from world.events import commit
from world.seed import rng_for


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


def drawn_assembly(game):
    import systems.events.grand_assembly as ga
    world, town = game.world, game.place.id
    commit(world, sky.start_events(world, "grand_assembly", town, world.time,
                                   ga.start_data(world, town, 10, rng_for(1, "a"))))
    occurrence = W.index(world)[-1][W.ID]
    world.set_time(T.day_start(world.entity(occurrence), 1))
    sky.observe(world, town)
    return occurrence


def test_a_finished_bracket_is_compacted_after_the_aftermath(game):
    world, town = game.world, game.place.id
    occurrence = drawn_assembly(game)
    world.set_time(world.entity(occurrence).data["over_at"] + 1)
    sky.observe(world, town)
    t = world.entity(occurrence).data["data"]
    assert t["finished"] and t["champion"] is not None and t["rounds"] == [] and t["compacted"]["entrants"] == 32
    assert len(t["compacted"]["semis"]) == 2 and t["compacted"]["runner_up"] not in (None, t["champion"])
    assert len(json.dumps(t)) < 2000
    assert any("Champion" in text for text, _ in bracket_lines(world, game.player.id, occurrence))
    assert check_tournaments(world) == []


def test_an_old_world_holds_its_first_assembly_at_the_next_cycle_point(game):
    """A save from before tournaments: nothing is backdated, and the first Assembly falls on its turn."""
    world = game.world
    offset = rng_for(world.world_seed, "sky:grand_assembly:offset").randrange(12)
    first = next(n for n in range(10, 40) if (n + offset) % 12 == 0)
    found = [n for n in range(10, first + 13) for e in sky.season_events(world, n)
             if e.kind == "sky_started" and e.data["type"] == "grand_assembly"]
    assert found == [first, first + 12]


def test_an_assembly_round_resolves_quickly(game):
    world = game.world
    occurrence = drawn_assembly(game)  # the player is at the venue: sixteen full duel simulations
    world.set_time(T.day_start(world.entity(occurrence), 2))
    start = time.process_time()
    T.resolve(world, occurrence)
    elapsed = time.process_time() - start
    assert all(m["how"] is not None for m in world.entity(occurrence).data["data"]["rounds"][0])
    assert elapsed < 0.06, f"a round took {elapsed * 1000:.0f} ms"


def test_the_fork_guide_covers_tournaments():
    guide = Path("docs/world-events.md").read_text(encoding="utf-8")
    for word in ("every", "stagger", "sky = false", "places", "summary", "on_observe", "T.KINDS", "qualifies",
                 "invite", "rewards", "CHANCES", "check_tournaments", "titles"):
        assert word in guide, word
