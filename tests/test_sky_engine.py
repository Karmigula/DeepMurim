import time

import pytest

import systems.encounters as encounters
import systems.rankings as R
import systems.world_events as W
from app import App
from config import Config
from engine.actions import Action
from engine.game import Game
from engine.rankings_page import rankings_lines
from engine.sheet import sheet_lines
from systems import founding
from systems.beliefs import believe
from systems.creation import CreationChoice
from systems.facts import make_variant, place_name, record_fact
from tests.test_rankings import deed, master, publish
from tests.test_world_events import begin
from world.events import commit
from world.gen.materialize import ensure_town, region_of


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.perform(Action("look"))
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def texts(turn):
    return [t for t, _ in turn.lines]


def moon(game):
    return begin(game.world, "blood_moon", None, starts=game.world.time - 6 * 4)


def test_the_scene_brief_carries_the_sky(game):
    moon(game)
    game.world.set_time(game.world.time + 1)  # a look at the same moment is "nothing has changed"
    game.perform(Action("look"))
    facts = " ".join(b for brief in game.last_briefs if brief.kind == "scene" for b in brief.facts)
    assert "blood moon" in facts and "days left" in facts


def test_a_new_stage_is_told_once(game):
    moon(game)
    first = texts(game.perform(Action("look")))
    assert any("blood moon" in t.lower() for t in first)
    again = texts(game.perform(Action("look")))
    assert not any("blood moon" in t.lower() for t in again)


def test_the_sky_page_shows_what_is_overhead_and_what_you_heard(game):
    world, me = game.world, game.player.id
    moon(game)
    far = ensure_town(world, 3, 3, 0)
    occurrence = begin(world, "qi_tide", region_of(world, far).id, starts=world.time - 11 * 4)
    variant = make_variant("phenomenon", far, None, place=place_name(world, far))
    variant.update(kind="qi_tide", stage="active", reading=None)
    fact = record_fact(world, far, "phenomenon", None, place=far, variant=variant, spread=False,
                       extra={"occurrence": occurrence, "until": world.time + 40 * 4})
    believe(world, me, fact, variant, None, 0.7, 2, "gossip")
    lines = texts(game.perform(Action("sky")))
    assert any("blood moon" in t for t in lines) and any("qi tide" in t and "days left" in t for t in lines)


def test_the_rankings_page_and_f10(game, tmp_path):
    world, me, town = game.world, game.player.id, game.place.id
    deed(world, me, "tribulation", town, realm="peak", age=20)
    publish(world)
    fact = world.facts(predicate="published")[-1]
    believe(world, me, fact.id, fact.variant, None, 1.0, 1, "posted")
    lines = texts(game.perform(Action("rankings")))
    assert any("You are First of Heaven" in t for t in lines) and any(t.startswith("Heaven") for t in lines)
    app = App(Config(), tmp_path / "saves", tmp_path / "settings.json")
    app.start_new("Watcher", world_seed=5)
    app.handle_key("f10", "")
    assert any("Pavilion" in t for t, _ in app.last_turn.lines)


def test_the_rankings_page_marks_the_dead_you_have_heard_of(game):
    world, me, town = game.world, game.player.id, game.place.id
    old = master(world, town, "test:old", realm="peak", age=80)
    deed(world, old, "tribulation", town, realm="peak")
    publish(world)
    for fact in (world.facts(predicate="published")[-1], world.fact(deed(world, old, "died", town, heard=False))):
        believe(world, me, fact.id, fact.variant, None, 1.0, 1, "gossip")
    assert any(world.entity(old).name in t and "dead" in t for t, _ in rankings_lines(world, me))


def test_a_city_posts_the_lists_when_you_arrive(game):
    world, me = game.world, game.player.id
    deed(world, master(world, game.place.id, "test:m"), "tribulation", game.place.id, realm="first-rate")
    publish(world)
    city = R.capital(world)
    world.unrelate(me, "located_in")
    world.relate(me, city, "located_in")
    game.perform(Action("look"))
    assert R.latest(world, me) is not None


def test_the_sheet_shows_the_heavens_and_your_rank(game):
    world, me, town = game.world, game.player.id, game.place.id
    begin(world, "qi_tide", region_of(world, town).id, starts=world.time - 11 * 4)
    text = " ".join(t for t, _ in sheet_lines(world, me))
    assert "Qi tide: breakthrough x1.2, cultivation x1.5" in text and "Rank: unranked" in text


def test_an_ancestors_rank_is_remembered_on_the_lineage_page(game):
    from engine.lineage_page import lineage_lines
    world, me, town = game.world, game.player.id, game.place.id
    grandmother = master(world, town, "test:grandmother", realm="peak", age=90)
    deed(world, grandmother, "tribulation", town, realm="peak")
    publish(world)
    world.update_data(grandmother, dead=True, death={"cause": "age", "age": 90, "place": town})
    world.update_data(me, ancestors=[grandmother])
    assert any("once First of Heaven" in t for t, _ in lineage_lines(world, me))


def test_a_crowded_menu_folds_its_tail_under_more(game, monkeypatch):
    from engine.actions import Choice
    extras = [Choice(f"Extra {i}", Action("look")) for i in range(10)]
    monkeypatch.setattr(type(game), "_general_extras", lambda self: extras)
    turn = game.perform(Action("look"))
    assert len(turn.choices) <= 9 and turn.choices[-1].label == "More..."
    more = game.perform(Action("more_menu"))
    assert any(c.label == "Extra 9" for c in more.choices) and more.choices[-1].label == "Back"


def test_the_rankings_page_is_quick(game):
    world, me, town = game.world, game.player.id, game.place.id
    for i in range(80):
        deed(world, master(world, town, f"test:q{i}"), "tribulation", town, realm="first-rate", age=20 + i % 30)
    publish(world)
    fact = world.facts(predicate="published")[-1]
    believe(world, me, fact.id, fact.variant, None, 1.0, 1, "posted")
    rankings_lines(world, me)
    start = time.process_time()
    rankings_lines(world, me)
    assert time.process_time() - start < 0.03
