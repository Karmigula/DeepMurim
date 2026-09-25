import random

import pytest

import systems.duel as duel
import systems.encounters as encounters
import systems.sky as sky
import systems.tournaments as T
import systems.wagers as wagers
import systems.world_events as W
from debug.invariants import check_tournaments
from engine.actions import Action
from engine.game import Game
from systems import founding
from systems.creation import CreationChoice
from systems.facts import make_variant, place_name, record_fact
from systems.purse import silver_of
from world.events import Event, commit
from world.seed import rng_for


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    g.world.set_time(10 * W.SEASON + 8)
    g.world.update_data(g.player.id, silver=1000)
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)


def drawn_assembly(game, registered=()):
    import systems.events.grand_assembly as ga
    world, town = game.world, game.place.id
    commit(world, sky.start_events(world, "grand_assembly", town, world.time,
                                   {**ga.start_data(world, town, 10, rng_for(1, "a")), "registered": list(registered)}))
    occurrence = W.index(world)[-1][W.ID]
    world.set_time(T.day_start(world.entity(occurrence), 1))
    sky.observe(world, town)
    return occurrence


def to_day(game, occurrence, k):
    game.world.set_time(T.day_start(game.world.entity(occurrence), k))
    sky.observe(game.world, game.place.id)


def match(world, occurrence, r, i):
    return world.entity(occurrence).data["data"]["rounds"][r][i]


def test_the_odds_follow_what_the_town_believes(game):
    world, town = game.world, game.place.id
    famous = founding.make_person(world, "test:famous", town, occupation="monk", age=40, realm="second-rate")
    for i in range(4):
        victim = founding.make_person(world, f"test:victim:{i}", town, occupation="monk", age=40)
        record_fact(world, famous, "defeated", victim, place=town, weight=3.0,
                    variant=make_variant("defeated", famous, victim, place=place_name(world, town)))
    occurrence = drawn_assembly(game, registered=[famous])
    r, i, m = next((r, i, m) for r, i, m in wagers.open_matches(world, occurrence) if famous in (m["a"], m["b"]))
    prices = wagers.odds(world, occurrence, r, i)
    other = m["b"] if m["a"] == famous else m["a"]
    assert prices[famous] < prices[other] and prices[famous] >= 1.0 - wagers.MARGIN


def test_a_winning_bet_pays_and_a_losing_one_does_not(game):
    world, me = game.world, game.player.id
    occurrence = drawn_assembly(game)
    r, i, m = wagers.open_matches(world, occurrence)[0]
    commit(world, wagers.bet_events(world, occurrence, r, i, m["a"], 50, me))
    commit(world, wagers.bet_events(world, occurrence, r, i, m["b"], 50, me))
    prices = wagers.odds(world, occurrence, r, i)
    silver = silver_of(world, me)
    to_day(game, occurrence, 2)
    winner = match(world, occurrence, r, i)["winner"]
    bets = world.entity(occurrence).data["data"]["bets"]
    assert all(b["settled"] for b in bets)
    assert silver_of(world, me) == silver + int(50 * next(b["odds"] for b in bets if b["on"] == winner))
    assert check_tournaments(world) == []


def test_the_stake_is_at_most_a_tenth_of_your_silver(game):
    world, me = game.world, game.player.id
    occurrence = drawn_assembly(game)
    r, i, m = wagers.open_matches(world, occurrence)[0]
    assert "tenth" in wagers.bet_block(world, occurrence, r, i, m["a"], 101, me)
    assert wagers.bet_block(world, occurrence, r, i, m["a"], 100, me) is None


def test_a_bet_on_a_walkover_settles_once(game):
    world, me = game.world, game.player.id
    occurrence = drawn_assembly(game)
    r, i, m = wagers.open_matches(world, occurrence)[0]
    commit(world, wagers.bet_events(world, occurrence, r, i, m["b"], 40, me))
    commit(world, wagers.bet_events(world, occurrence, r, i, m["a"], 40, me))
    world.update_data(m["b"], dead=True)
    to_day(game, occurrence, 2)
    to_day(game, occurrence, 4)
    bets = world.entity(occurrence).data["data"]["bets"]
    settled = [e for e in world.chronicle_about(me, limit=100) if e.kind == "bet_settled"]
    assert len(settled) == 2 and all(b["settled"] for b in bets)
    assert [b["payout"] for b in bets] == [0, int(40 * bets[1]["odds"])]


def test_betting_on_your_rival_and_losing_is_a_scandal(game):
    world, me = game.world, game.player.id
    from systems.bodies import load_body, save_body
    body = load_body(world, me)
    body.realm = 2
    save_body(world, me, body)
    occurrence = drawn_assembly(game, registered=[me])
    call = T.player_call(world, me, game.place.id)
    _, r, i, rival = call
    commit(world, wagers.bet_events(world, occurrence, r, i, rival, 50, me))
    game.perform(Action("forfeit_bout", occurrence))
    assert world.facts(predicate="fixed", subject=me)


def test_a_bettors_death_voids_and_refunds(game):
    world, me, town = game.world, game.player.id, game.place.id
    occurrence = drawn_assembly(game)
    r, i, m = wagers.open_matches(world, occurrence)[0]
    commit(world, wagers.bet_events(world, occurrence, r, i, m["a"], 60, me))
    silver = silver_of(world, me)
    commit(world, [Event("died", (me, me), town, {"cause": "age"})])
    bet = world.entity(occurrence).data["data"]["bets"][0]
    assert bet["settled"] and bet["payout"] == 60 and silver_of(world, me) == silver + 60


def test_the_bookmaker_takes_bets_at_the_venue(game):
    world, me = game.world, game.player.id
    occurrence = drawn_assembly(game)
    turn = game.perform(Action("look"))
    assert Action("bookmaker", occurrence) in [c.action for c in turn.all_choices]
    board = game.perform(Action("bookmaker", occurrence))
    bets = [c.action for c in board.choices if c.action.verb == "bet"]
    assert bets and any("odds" in t or "to 1" in t for t, _ in board.lines)
    game.perform(bets[0])
    assert world.entity(occurrence).data["data"]["bets"][0]["stake"] == 100  # a tenth of the 1000 silver held


def test_the_rules_catch_an_open_bet_after_the_end(game):
    world, me = game.world, game.player.id
    occurrence = drawn_assembly(game)
    r, i, m = wagers.open_matches(world, occurrence)[0]
    commit(world, wagers.bet_events(world, occurrence, r, i, m["a"], 10, me))
    to_day(game, occurrence, 9)
    t = dict(world.entity(occurrence).data["data"])
    t["bets"] = [dict(t["bets"][0], settled=False)]
    world.update_data(occurrence, data=t)
    assert any("open bet" in p for p in check_tournaments(world))
