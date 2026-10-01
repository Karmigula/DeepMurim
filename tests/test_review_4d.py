"""Phase 4d final review: each fix pinned by a test that failed first."""

import pytest

import systems.rankings as R
import systems.sky as sky
import systems.world_events as W
from engine.game import Game
from systems.beliefs import believe
from systems.creation import CreationChoice
from tests.test_rankings import deed, master, publish
from tests.test_world_events import add_type, begin


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.set_time(3 * W.SEASON + 8)
    yield g
    g.close()


def test_a_master_the_pavilion_has_not_heard_of_in_forty_years_drops_off(game):
    world, town = game.world, game.place.id
    hermit = master(world, town, "test:hermit", realm="peak", age=40)
    deed(world, hermit, "tribulation", town, realm="peak", age=40)
    assert hermit in R.scores(world, R.ensure_pavilion(world))
    world.set_time(world.time + (R.SILENCE_YEARS + 1) * R.YEAR)
    assert hermit not in R.scores(world, R.ensure_pavilion(world))


def test_a_master_believed_past_their_lifespan_drops_off(game):
    world, town = game.world, game.place.id
    old = master(world, town, "test:ancient", realm="second-rate", age=90)
    deed(world, old, "tribulation", town, realm="second-rate", age=90)
    world.set_time(world.time + 10 * R.YEAR)
    assert old not in R.scores(world, R.ensure_pavilion(world))


def test_an_npc_kill_counts_as_a_win(game):
    world, town = game.world, game.place.id
    killer, victim = master(world, town, "test:killer"), master(world, town, "test:victim")
    deed(world, victim, "tribulation", town, realm="first-rate")
    publish(world)
    before = R.scores(world, R.ensure_pavilion(world))[victim]
    deed(world, killer, "killed", town, realm="first-rate", target=victim)
    table = R.scores(world, R.ensure_pavilion(world))
    assert table[killer] == pytest.approx(300 + R.WIN_POINTS + R.WIN_SHARE * before) and victim not in table


def test_the_published_belief_carries_no_copy_of_the_lists(game):
    world, me, town = game.world, game.player.id, game.place.id
    champion = master(world, town, "test:champion", realm="peak")
    deed(world, champion, "tribulation", town, realm="peak")
    publish(world)
    fact = world.facts(predicate="published")[-1]
    assert "lists" not in fact.variant and fact.variant["first"] == champion
    believe(world, me, fact.id, fact.variant, town, 0.8, 2, "gossip")
    assert R.latest(world, me)["lists"]["heaven"][0] == champion
    stored = world._conn.execute("select variant from beliefs where fact_id = ? and knower = ?", (fact.id, me)).fetchone()[0]
    assert len(stored) < 300


def test_a_stage_already_over_makes_no_news(game, monkeypatch):
    add_type(monkeypatch, "omen", scope="town", cycle="trigger", stages={"announced": 2, "active": 5},
             news={"predicate": "phenomenon", "weight": 1.2, "stages": ["announced", "active"]})
    world, town = game.world, game.place.id
    begin(world, "omen", town)
    world.set_time(world.time + 3 * 4)  # the announcement ended a day ago; only the active stage is news
    sky.observe(world, town)
    assert [f.variant["stage"] for f in world.facts(predicate="phenomenon", subject=town)] == ["active"]


@pytest.mark.parametrize("spec", [{"stages": {"actve": 3}}, {"modifier": {"cultivation": 1.2}}])
def test_a_misspelt_event_type_is_refused(spec):
    with pytest.raises(ValueError):
        W.full_spec(spec)
