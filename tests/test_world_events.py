import json
import time

import pytest

import systems.market as market
import systems.sky as sky
import systems.world_events as W
from debug.invariants import check_sky
from engine.game import Game
from narrate.gossip_text import rumour_text
from systems.creation import CreationChoice
from world.events import commit
from world.gen.materialize import ensure_town, region_of


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def add_type(monkeypatch, name, **spec):
    monkeypatch.setitem(W.TYPES, name, W.full_spec(spec))


def begin(world, kind, place, starts=None, **data):
    events = sky.start_events(world, kind, place, world.time if starts is None else starts, data)
    assert events, f"{kind} did not start"
    commit(world, events)
    return W.index(world)[-1][W.ID]


def stages_seen(world, occurrence):
    rows = world._conn.execute("select data from chronicle where kind = 'world_event_stage' order by id").fetchall()
    return [d["stage"] for d in map(lambda r: json.loads(r[0]), rows) if d["occurrence"] == occurrence]


OMEN = dict(scope="town", cycle="trigger", stages={"foretold": 2, "announced": 3, "active": 5, "aftermath": 4})


def test_stages_follow_the_calendar(game, monkeypatch):
    add_type(monkeypatch, "omen", **OMEN)
    world, t0 = game.world, game.world.time
    data = world.entity(begin(world, "omen", game.place.id)).data
    assert [W.stage_at(data, t0 + d * 4) for d in (0, 2, 5, 9, 10, 13, 14)] == \
        ["foretold", "announced", "active", "active", "aftermath", "aftermath", "over"]
    assert W.stage_at(data, t0 - 1) == "pending"


def test_each_stage_is_observed_once(game, monkeypatch):
    add_type(monkeypatch, "omen", **OMEN)
    world, t0 = game.world, game.world.time
    occurrence = begin(world, "omen", game.place.id)
    for day in (0, 3, 3, 11, 20, 20):
        world.set_time(t0 + day * 4)
        sky.observe(world, game.place.id)
    assert stages_seen(world, occurrence) == ["foretold", "announced", "active", "aftermath", "over"]
    assert world.entity(occurrence).data["over"] and W.index(world)[-1][W.DONE]
    assert check_sky(world) == []


def test_a_catch_up_starts_nothing_already_over(game, monkeypatch):
    add_type(monkeypatch, "tide", scope="region", chance=1.0, stages={"active": 200})
    world = game.world
    world.set_time(world.time + 20 * W.SEASON)
    now = world.time // W.SEASON
    assert [e for e in sky.season_events(world, now - 5) if e.data["type"] == "tide"] == []
    assert [e for e in sky.season_events(world, now) if e.data["type"] == "tide"]


def test_modifiers_multiply_and_clamp(game, monkeypatch):
    add_type(monkeypatch, "calm", scope="world", cycle="trigger", stages={"active": 30}, modifiers={"cultivation": 1.5})
    add_type(monkeypatch, "storm", scope="region", cycle="trigger", stages={"active": 30}, modifiers={"cultivation": 4.0})
    add_type(monkeypatch, "drain", scope="town", cycle="trigger", stages={"active": 30}, modifiers={"cultivation": 0.01})
    world, town = game.world, game.place.id
    far = ensure_town(world, 5, 5, 0)
    assert W.factor(world, town, "cultivation") == 1.0
    begin(world, "calm", None)
    assert W.factor(world, town, "cultivation") == 1.5 and W.factor(world, None, "cultivation") == 1.5
    begin(world, "storm", region_of(world, town).id)
    assert W.factor(world, town, "cultivation") == 4.0
    assert W.factor(world, far, "cultivation") == 1.5
    begin(world, "drain", town)
    assert W.factor(world, town, "cultivation") == 0.25
    assert W.factor(world, town, "breakthrough") == 1.0
    world.set_time(world.time + 31 * 4)
    assert W.factor(world, town, "cultivation") == 1.0


def test_one_live_occurrence_per_type_per_place(game, monkeypatch):
    add_type(monkeypatch, "omen", **OMEN)
    begin(game.world, "omen", game.place.id)
    assert sky.start_events(game.world, "omen", game.place.id, game.world.time) == []
    assert sky.start_events(game.world, "omen", ensure_town(game.world, 1, 0, 0), game.world.time)


def test_an_old_world_has_a_quiet_sky(game):
    assert W.index(game.world) == [] and W.factor(game.world, game.place.id, "cultivation") == 1.0
    assert check_sky(game.world) == []


def test_a_type_from_toml_runs_its_module(game, monkeypatch, tmp_path):
    import tests.sky_fork_example as fork
    monkeypatch.setattr(W, "TYPES", dict(W.TYPES))
    path = tmp_path / "fork.toml"
    path.write_text('[fork_omen]\nmodule = "tests.sky_fork_example"\nscope = "town"\ncycle = "trigger"\n'
                    'stages = { active = 3 }\n', encoding="utf-8")
    W.load_types(path)
    fork.SEEN.clear()
    world = game.world
    begin(world, "fork_omen", game.place.id)
    world.set_time(world.time + 20)
    sky.observe(world)
    assert fork.SEEN == ["active", "over"]


def test_news_carries_a_local_reading(game, monkeypatch):
    add_type(monkeypatch, "omen", scope="town", cycle="trigger", stages={"announced": 2, "active": 5},
             readings=["war", "plenty"], news={"predicate": "phenomenon", "weight": 1.2, "stages": ["announced"]})
    world, town = game.world, game.place.id
    begin(world, "omen", town)
    sky.observe(world, town)
    [fact] = world.facts(predicate="phenomenon", subject=town)
    assert fact.variant["kind"] == "omen" and fact.variant["stage"] == "announced"
    assert fact.variant["reading"] in ("war", "plenty") and fact.data["occurrence"]
    text = rumour_text(world, fact.variant, game.player.id)
    assert "omen" in text and "{" not in text


def test_prices_follow_the_sky(game, monkeypatch):
    add_type(monkeypatch, "dearth", scope="town", cycle="trigger", stages={"active": 30}, prices={"salt": 2.0})
    world, town = game.world, game.place.id
    before = market.price(world, town, "salt")
    begin(world, "dearth", town)
    assert market.price(world, town, "salt") == pytest.approx(before * 2, abs=1)


def test_the_sky_rules_catch_a_broken_calendar(game, monkeypatch):
    add_type(monkeypatch, "omen", **OMEN)
    world = game.world
    occurrence = begin(world, "omen", game.place.id)
    assert check_sky(world) == []
    world.update_data(occurrence, seen=["active", "foretold"])
    assert any("out of order" in p for p in check_sky(world))


def test_the_narrator_never_repeats_a_line_of_another_kind():
    from dataclasses import replace
    from narrate.procedural import Grammar, ProceduralNarrator
    from tests.test_narrate import brief
    narrator = ProceduralNarrator(Grammar({"a": {"lines": ["#x#"]}, "b": {"lines": ["#x#"]},
                                           "symbols": {"x": ["One.", "Two."]}}))
    [(first, _)] = narrator.narrate(brief("a"))
    [(second, _)] = narrator.narrate(replace(brief("b"), salt="t:b:1"))
    assert first != second


def test_a_name_that_is_also_a_word_is_matched_by_its_capital(game):
    from types import SimpleNamespace
    from debug.invariants import check_people
    stranger = game.world.add_entity("person", "Again", {"age": 30, "occupation": "monk"})
    game.world.relate(stranger, ensure_town(game.world, 4, 4, 0), "located_in")
    quiet = SimpleNamespace(lines=[("Until the rivers meet again.", "npc")], all_choices=[])
    loud = SimpleNamespace(lines=[("Again the monk bows.", "npc")], all_choices=[])
    assert check_people(game, quiet) == []
    assert any("Again" in p for p in check_people(game, loud))


def test_factor_is_quick(game, monkeypatch):
    add_type(monkeypatch, "storm", scope="region", cycle="trigger", stages={"active": 30}, modifiers={"cultivation": 1.1})
    world = game.world
    for x in range(20):
        begin(world, "storm", region_of(world, ensure_town(world, x, 3, 0)).id)
    town = game.place.id
    start = time.process_time()
    for _ in range(1000):
        W.factor(world, town, "cultivation")
    assert time.process_time() - start < 0.2
