import random

import pytest

import systems.duel as duel
import systems.encounters as encounters
import systems.sky as sky
import systems.tournaments as T
import systems.world_events as W
from debug.invariants import check_tournaments
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.purse import silver_of
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


def texts(turn):
    return [t for t, _ in turn.lines]


def actions(turn):
    return [c.action for c in turn.all_choices]


def start(world, kind, town, data):
    commit(world, sky.start_events(world, kind, town, world.time, data))
    return W.index(world)[-1][W.ID]


def second_rate(game):
    body = load_body(game.world, game.player.id)
    body.realm = 2
    save_body(game.world, game.player.id, body)


def announced_assembly(game):
    import systems.events.grand_assembly as ga
    world, town = game.world, game.place.id
    occurrence = start(world, "grand_assembly", town, ga.start_data(world, town, 10, rng_for(1, "a")))
    world.set_time(world.entity(occurrence).data["ends"]["foretold"] + 1)
    return occurrence


def entered(game):
    second_rate(game)
    game.world.update_data(game.player.id, silver=500)
    occurrence = announced_assembly(game)
    game.perform(Action("register", occurrence))
    return occurrence


def to_day(game, occurrence, k):
    game.world.set_time(T.day_start(game.world.entity(occurrence), k))
    return game.perform(Action("look"))


def finish(game, result, verdict=None):
    d = game.combat
    event = duel._end_event(game.world, d, result, "broken", random.Random(1), d.harm, 5, verdict=verdict)
    game._commit([event])
    return game._finish_duel(event.data)


def my_match(world, occurrence, me):
    t = world.entity(occurrence).data["data"]
    return next(((r, i, m) for r, ms in enumerate(t["rounds"]) for i, m in enumerate(ms) if me in (m["a"], m["b"])
                 and m["how"] is None), None)


def test_registering_follows_the_rules(game):
    world, me = game.world, game.player.id
    occurrence = announced_assembly(game)
    assert "Second-rate" in T.register_block(world, occurrence, me)
    second_rate(game)
    world.update_data(me, silver=0)
    assert "bond" in T.register_block(world, occurrence, me)
    world.update_data(me, silver=150)
    assert Action("register", occurrence) in actions(game.perform(Action("look")))
    game.perform(Action("register", occurrence))
    t = world.entity(occurrence).data["data"]
    assert me in t["registered"] and silver_of(world, me) == 50 and t["bonds"][str(me)] == 100
    assert "already" in T.register_block(world, occurrence, me)


def test_registration_closes_when_the_bout_days_begin(game):
    second_rate(game)
    occurrence = announced_assembly(game)
    game.world.set_time(T.day_start(game.world.entity(occurrence), 1))
    assert "not open" in T.register_block(game.world, occurrence, game.player.id)


def test_the_herald_calls_you_and_a_win_advances_you(game):
    world, me = game.world, game.player.id
    occurrence = entered(game)
    turn = to_day(game, occurrence, 1)
    assert any("herald" in t.lower() for t in texts(turn)) and Action("bout", occurrence) in actions(turn)
    game.perform(Action("bout", occurrence))
    assert game.combat is not None and game.combat.mode == "bout"
    finish(game, "won", verdict="spare")
    r, i, m = my_match(world, occurrence, me)
    assert r == 1 and world.entity(occurrence).data["data"]["rounds"][0][
        next(j for j, x in enumerate(world.entity(occurrence).data["data"]["rounds"][0]) if me in (x["a"], x["b"]))]["how"] == "bout"
    assert check_tournaments(world) == []


def test_a_kill_in_a_bout_disqualifies_and_disgraces(game):
    world, me = game.world, game.player.id
    occurrence = entered(game)
    to_day(game, occurrence, 1)
    game.perform(Action("bout", occurrence))
    victim = game.combat.opponent
    game.combat.stage = "verdict"
    game.perform(Action("verdict", "kill"))
    t = world.entity(occurrence).data["data"]
    assert me in t["disqualified"] and world.facts(predicate="disgraced", subject=me)
    assert world.entity(victim).data.get("dead") and my_match(world, occurrence, me) is None
    assert check_tournaments(world) == []


def test_missing_your_day_forfeits_and_the_bracket_goes_on(game):
    world, me = game.world, game.player.id
    occurrence = entered(game)
    to_day(game, occurrence, 1)
    to_day(game, occurrence, 4)
    t = world.entity(occurrence).data["data"]
    mine = next(m for m in t["rounds"][0] if me in (m["a"], m["b"]))
    assert mine["how"] == "forfeit" and mine["winner"] != me
    assert all(m["how"] is not None for m in t["rounds"][1])
    to_day(game, occurrence, 9)
    assert world.entity(occurrence).data["data"]["finished"] and check_tournaments(world) == []


def test_forfeiting_gives_the_match_away(game):
    world, me = game.world, game.player.id
    occurrence = entered(game)
    to_day(game, occurrence, 1)
    game.perform(Action("forfeit_bout", occurrence))
    mine = next(m for m in world.entity(occurrence).data["data"]["rounds"][0] if me in (m["a"], m["b"]))
    assert mine["how"] == "forfeit" and mine["winner"] != me


def test_the_bond_comes_back_after_the_first_round(game):
    world, me = game.world, game.player.id
    occurrence = entered(game)
    silver = silver_of(world, me)
    to_day(game, occurrence, 1)
    game.perform(Action("bout", occurrence))
    finish(game, "won", verdict="spare")
    assert silver_of(world, me) == silver + 100


def test_presiding_keeps_you_out_of_the_bracket(game):
    import systems.events.sect_contest as sc
    from tests.test_sect import found_sect
    world, me = game.world, game.player.id
    sect, town = found_sect(game)
    for i in range(2):
        founding.enrol(world, founding.make_person(world, f"test:extra:{i}", town), sect, 70)
    occurrence = start(world, "sect_contest", town, sc.start_data(world, town, 10, rng_for(1, "s")))
    assert T.can_preside(world, occurrence, me)
    game.perform(Action("preside", occurrence))
    world.set_time(world.entity(occurrence).data["over_at"] + 1)
    sky.observe(world, town)
    t = world.entity(occurrence).data["data"]
    assert t["presiding"] == me and me not in t["entrants"] and t["finished"]


def test_same_day_rounds_let_you_fight_on(game):
    import systems.events.sect_contest as sc
    world, me, town = game.world, game.player.id, game.place.id
    school = next(f.id for f in world.entities("faction") if f.data["type"] == "school")
    world.relate(me, school, "member_of", 1, {"role": "disciple", "hall": None, "merit": 0, "status": "member",
                                              "secret": False})
    occurrence = start(world, "sect_contest", town, sc.start_data(world, town, 10, rng_for(1, "s")))
    game.perform(Action("register", occurrence))
    to_day(game, occurrence, 1)
    first = T.player_call(world, me, town)
    assert first is not None
    game.perform(Action("bout", occurrence))
    finish(game, "won", verdict="spare")
    second = T.player_call(world, me, town)
    assert second is not None and second[1] == first[1] + 1  # the next round is fought the same day


def test_you_may_challenge_the_lei_tai_holder_once(game):
    import systems.events.lei_tai as lt
    world, me, town = game.world, game.player.id, game.place.id
    for i in range(3):
        founding.make_person(world, f"test:brawler:{i}", town, occupation="wandering swordsman", age=30,
                             realm="third-rate")
    occurrence = start(world, "lei_tai", town, lt.start_data(world, town, 10, rng_for(1, "l")))
    turn = game.perform(Action("look"))
    assert Action("challenge_lei_tai", occurrence) in actions(turn)
    game.perform(Action("challenge_lei_tai", occurrence))
    finish(game, "won", verdict="spare")
    t = world.entity(occurrence).data["data"]
    assert t["holder"] == me and me in t["challenged"]
    assert Action("challenge_lei_tai", occurrence) not in actions(game.perform(Action("look")))
    silver = silver_of(world, me)
    world.set_time(world.entity(occurrence).data["over_at"] + 1)
    game.perform(Action("look"))
    assert silver_of(world, me) == silver + t["purse"]


def test_the_rules_catch_a_spared_loser_killed_by_the_winner(game):
    world, me = game.world, game.player.id
    occurrence = entered(game)
    to_day(game, occurrence, 1)
    game.perform(Action("bout", occurrence))
    victim = game.combat.opponent
    finish(game, "won", verdict="spare")
    world.update_data(victim, dead=True, death={"cause": "killed", "killer": me})
    assert any("killed" in p for p in check_tournaments(world))
