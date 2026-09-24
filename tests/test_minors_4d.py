"""Phase 4d deferred minors, each pinned by a test that failed first."""
import subprocess
import sys

import pytest

import systems.lives as lives
import systems.rankings as R
import systems.sky as sky
import systems.wars as wars
import systems.world_clock as world_clock
import systems.world_events as W
from debug.invariants import check_races
from engine.actions import Action
from engine.game import Game
from engine.rankings_page import rankings_lines
from engine.sky import sheet_sky_lines
from systems import founding
from systems.beliefs import believe
from systems.creation import CreationChoice
from tests.test_rankings import deed, master, publish
from tests.test_world_events import add_type, begin
from world.events import Event, commit
from world.gen.materialize import region_of


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.set_time(10 * W.SEASON + 8)
    yield g
    g.close()


def test_two_knobs_on_one_roll_are_clamped_together(game, monkeypatch):
    add_type(monkeypatch, "red", scope="world", cycle="trigger", stages={"active": 30}, modifiers={"encounter": 3.0})
    add_type(monkeypatch, "wild", scope="world", cycle="trigger", stages={"active": 30}, modifiers={"beasts": 3.0})
    begin(game.world, "red", None)
    begin(game.world, "wild", None)
    assert W.factors(game.world, game.place.id, ("encounter", "beasts")) == W.FACTOR_MAX


def test_season_hooks_run_in_the_same_order_whatever_was_imported_first(monkeypatch):
    blocks = {}
    for hook in world_clock.SEASON_HOOKS:
        blocks.setdefault(hook.__module__, []).append(hook)
    shuffled = [h for m in reversed(list(blocks)) for h in blocks[m]]  # another import order: modules move, not hooks
    monkeypatch.setattr(world_clock, "SEASON_HOOKS", shuffled)
    order = [(h.__module__, h.__name__) for h in world_clock.season_hooks()]
    assert order == sorted(order, key=lambda p: p[0])
    names = [n for m, n in order if m == "systems.sky"]
    assert names == ["season_events", "observe_all"]


@pytest.mark.parametrize("day", [0, 5, 15, 16, 59, 61, 89])
def test_every_comet_reaches_a_clash_roll(game, day):
    world = game.world
    n = world.time // W.SEASON
    begin(world, "comet", None, starts=n * W.SEASON + day * 4)
    assert any(wars.clash_boost(world, m) > 1.0 for m in (n + 1, n + 2))


def test_a_ranked_mask_is_you_on_the_sheet_and_the_page(game):
    world, me, town = game.world, game.player.id, game.place.id
    mask = world.add_entity("persona", "the Masked Crane", {"of": me})
    deed(world, mask, "tribulation", town, realm="peak", age=30)
    publish(world)
    fact = world.facts(predicate="published")[-1]
    believe(world, me, fact.id, fact.variant, None, 1.0, 1, "posted")
    assert any("Rank: First of Heaven" in t for t, _ in sheet_sky_lines(world, me))
    assert any("you, as the Masked Crane" in t for t, _ in rankings_lines(world, me))


def test_the_journal_does_not_tell_you_a_rank_you_never_heard(game):
    from engine.journal import summarize
    world, me, town = game.world, game.player.id, game.place.id
    deed(world, me, "tribulation", town, realm="peak", age=20)
    publish(world)
    entry = next(e for e in world.chronicle_about(me, limit=20) if e.kind == "rankings_published")
    assert "named you" not in summarize(world, entry)
    fact = world.facts(predicate="published")[-1]
    believe(world, me, fact.id, fact.variant, None, 1.0, 1, "posted")
    assert "named you First of Heaven" in summarize(world, entry)


def test_a_dao_resonance_halves_the_days_of_study(game):
    import systems.learning as learning
    from systems.items import create_manual
    from systems.techniques import create_technique, generate
    from world.seed import rng_for
    world, me, town = game.world, game.player.id, game.place.id
    name, data = generate(rng_for(1, "m"), "martial", grade=1)
    item = create_manual(world, me, create_technique(world, name, data), 1.0)
    plain = learning.study_events(world, me, town, item)[0].data["days"]
    master(world, town, "test:sage", realm="first-rate")
    import systems.events.dao_resonance as dao
    begin(world, "dao_resonance", town, **dao.start_data(world, town, 0, rng_for(1, "t")))
    assert learning.study_events(world, me, town, item)[0].data["days"] == max(1, round(plain / 2))


def test_a_type_registered_later_has_its_module_loaded_before_it_matters(game, monkeypatch):
    monkeypatch.setattr(W, "TYPES", dict(W.TYPES))
    monkeypatch.delitem(sys.modules, "tests.sky_late_example", raising=False)
    W.register("late_omen", {"module": "tests.sky_late_example", "scope": "town", "cycle": "trigger",
                             "stages": {"active": 3}})
    sky.observe(game.world)
    assert "tests.sky_late_example" in sys.modules


def test_the_fork_guide_warns_of_collisions_and_names_the_saved_state():
    from pathlib import Path
    guide = Path("docs/world-events.md").read_text(encoding="utf-8")
    for word in ("collide", "sky_index", "capital", "pavilion", "pavilion_mark", "pavilion_retry"):
        assert word in guide, word


@pytest.mark.parametrize("module", ["narrate.sky_text", "engine.sky"])
def test_the_sky_modules_import_on_their_own(module):
    subprocess.run([sys.executable, "-c", f"import {module}"], check=True, capture_output=True)


def test_an_early_rank_survives_a_long_life(game):
    world, town = game.world, game.place.id
    grandmother = master(world, town, "test:grandmother", realm="peak", age=40)
    deed(world, grandmother, "tribulation", town, realm="peak")
    publish(world)
    commit(world, [Event("met", (grandmother, game.player.id), town, {}) for _ in range(450)])
    assert R.best_rank(world, grandmother) == "First of Heaven"


def test_the_race_rules_still_see_a_race_the_index_forgot(game):
    import systems.races as races
    from world.seed import rng_for
    world = game.world
    occurrence = begin(world, "treasure_light", game.place.id, **races.race_start_data("treasure_light", rng_for(1, "x")))
    race = dict(world.entity(occurrence).data["data"], claimed=game.player.id, item=999999)
    world.update_data(occurrence, data=race)
    world.set_meta("sky_index", [])
    assert any("prize is missing" in p for p in check_races(world))
