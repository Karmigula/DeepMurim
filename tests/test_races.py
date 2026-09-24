import random

import pytest

import systems.duel as duel
import systems.encounters as encounters
import systems.mortality as mortality
import systems.races as races
import systems.sky as sky
import systems.world_events as W
from debug.invariants import check_races
from engine.actions import Action
from engine.game import Game
from systems.bodies import load_body
from systems.creation import CreationChoice
from systems.purse import silver_of
from tests.test_world_events import begin
from world.gen.materialize import ensure_town
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
    monkeypatch.setattr(races, "WANDERER_CHANCE", 1.0)
    monkeypatch.setattr(mortality, "lethal", lambda *args: None)


def texts(turn):
    return [t for t, _ in turn.lines]


def light(game, town=None, seed="t"):
    town = game.place.id if town is None else town
    occurrence = begin(game.world, "treasure_light", town, **races.race_start_data("treasure_light", rng_for(1, seed)))
    game.world.set_time(game.world.time + 6 * 4)
    sky.observe(game.world, town)
    return occurrence


def race(world, occurrence):
    return world.entity(occurrence).data["data"]


def finish(game, result):
    d = game.combat
    event = duel._end_event(game.world, d, result, "broken", random.Random(1), d.harm, 3,
                            verdict="spare" if result == "won" else None)
    game._commit([event])
    return game._finish_duel(event.data)


def test_a_treasure_light_calls_champions_who_fight_for_it(game):
    world = game.world
    occurrence = light(game)
    champions = race(world, occurrence)["champions"]
    assert len(champions) >= 2
    world.set_time(world.time + 21 * 4)
    sky.observe(world, game.place.id)
    winner = race(world, occurrence)["claimed"]
    assert winner in champions and world.targets(winner, "owns") and race(world, occurrence)["item"]
    assert world.facts(predicate="treasure", subject=winner)
    assert check_races(world) == []


def test_only_the_strongest_few_answer(game, monkeypatch):
    monkeypatch.setattr(races, "MAX_CHAMPIONS", 1)
    occurrence = light(game)
    assert len(race(game.world, occurrence)["champions"]) == 1


def test_the_contest_is_the_same_every_time(tmp_path):
    winners = []
    for n in range(2):
        g = Game.new(tmp_path / f"g{n}.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
        g.start()
        g.world.set_time(10 * W.SEASON + 8)
        occurrence = light(g)
        g.world.set_time(g.world.time + 21 * 4)
        sky.observe(g.world, g.place.id)
        winners.append(race(g.world, occurrence)["claimed"])
        g.close()
    assert winners[0] == winners[1] is not None


def test_seek_fights_each_champion_and_claims_the_prize(game):
    world, me = game.world, game.player.id
    occurrence = light(game)
    champions = race(world, occurrence)["champions"]
    for champion in reversed(champions):  # the weakest first
        turn = game.perform(Action("seek"))
        assert game.combat is not None and game.combat.opponent == champion, texts(turn)
        lines = finish(game, "won")
    assert race(world, occurrence)["claimed"] == me
    assert race(world, occurrence)["item"] in world.targets(me, "owns")
    assert any("claim" in t.lower() for t, _ in lines)


def test_a_prize_is_never_claimed_twice(game):
    world, me = game.world, game.player.id
    occurrence = light(game)
    for _ in race(world, occurrence)["champions"]:
        game.perform(Action("seek"))
        finish(game, "won")
    assert races.claim_events(world, occurrence, me, game.place.id) == []
    world.set_time(world.time + 21 * 4)
    sky.observe(world, game.place.id)
    item = race(world, occurrence)["item"]
    assert world.sources(item, "owns") == [me] and check_races(world) == []


def test_losing_puts_you_out_of_the_race(game):
    occurrence = light(game)
    game.perform(Action("seek"))
    finish(game, "lost")
    assert game.player.id in race(game.world, occurrence)["out"]
    assert any("had your chance" in t for t in texts(game.perform(Action("seek"))))


def test_seek_far_from_the_light_points_the_way(game):
    far = ensure_town(game.world, 1, 0, 0)
    light(game, town=far)
    lines = texts(game.perform(Action("seek")))
    assert any(game.world.entity(far).name in t and "1 region" in t for t in lines), lines


def test_a_pill_is_swallowed_and_a_herb_is_sold(game):
    world, me = game.world, game.player.id
    pill = races.make_prize(world, me, {"kind": "pill", "name": "a Purple Cloud Pill", "qi_years": 0.5, "value": 75}, 0)
    herb = races.make_prize(world, me, {"kind": "herb", "name": "a blood lotus", "value": 300}, 0)
    energy, silver = load_body(world, me).energy_years, silver_of(world, me)
    choices = [c.action for c in game.perform(Action("look")).all_choices]
    assert Action("swallow", pill) in choices and Action("sell_treasure", herb) in choices
    game.perform(Action("swallow", pill))
    game.perform(Action("sell_treasure", herb))
    assert load_body(world, me).energy_years > energy and silver_of(world, me) == silver + 300
    assert world.sources(pill, "owns") == [] and world.entity(pill).data["used"]
    assert world.sources(herb, "owns") == [game.place.id]
    assert check_races(world) == []


def test_the_race_rules_catch_a_prize_with_two_owners(game):
    world, me = game.world, game.player.id
    herb = races.make_prize(world, me, {"kind": "herb", "name": "a blood lotus", "value": 300}, 0)
    world.relate(game.place.id, herb, "owns")
    assert any("owners" in p for p in check_races(world))
