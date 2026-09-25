"""Phase 4e final review: the Important findings, each pinned by a test."""

import pytest

import systems.arena as arena
import systems.encounters as encounters
import systems.intrigue as intrigue
import systems.sky as sky
import systems.tournaments as T
import systems.wagers as wagers
import systems.world_events as W
from engine.game import Game
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
    monkeypatch.setitem(intrigue.CHANCES, "grand_assembly", ())  # no dark plots: these tests are about the straight game


def drawn_assembly(game):
    import systems.events.grand_assembly as ga
    world, town = game.world, game.place.id
    commit(world, sky.start_events(world, "grand_assembly", town, world.time,
                                   ga.start_data(world, town, 10, rng_for(1, "a"))))
    occurrence = W.index(world)[-1][W.ID]
    world.set_time(T.day_start(world.entity(occurrence), 1))
    sky.observe(world, town)
    return occurrence


def test_a_fighter_gone_mid_tournament_walks_over_and_is_neither_watched_nor_bet_on(game):
    world, me, town = game.world, game.player.id, game.place.id
    occurrence = drawn_assembly(game)
    r, i, m = wagers.open_matches(world, occurrence)[0]
    world.update_data(m["a"], dead=True)  # killed in a street duel between two looks
    assert (r, i) not in {(rr, ii) for rr, ii, _ in wagers.open_matches(world, occurrence)}
    found = arena.watchable(world, occurrence, me)
    assert found is None or found[:2] != (r, i)
    sky.observe(world, town)
    settled = world.entity(occurrence).data["data"]["rounds"][r][i]
    assert settled["how"] == "walkover" and settled["winner"] == m["b"]  # at once, not when the day has passed


def test_the_odds_stay_within_a_bookmakers_bounds(game, monkeypatch):
    world = game.world
    occurrence = drawn_assembly(game)
    r, i, m = wagers.open_matches(world, occurrence)[0]
    monkeypatch.setattr(T, "strengths", lambda world, town, people: {m["a"]: 3000.0, m["b"]: 0.0})  # listed v unknown
    prices = wagers.odds(world, occurrence, r, i)
    assert prices[m["a"]] >= wagers.MIN_ODDS  # a winning bet always returns more than its stake
    assert prices[m["b"]] <= (1 - wagers.MARGIN) / wagers.P_BOUNDS[0]  # no 2700 to 1 on a stranger


def test_an_elders_invitation_keeps_the_membership_rules(game, monkeypatch):
    from engine.actions import Action
    from systems import factions as F
    monkeypatch.setattr(arena, "NOTICE_BASE", 5.0)
    world, me = game.world, game.player.id
    occurrence = drawn_assembly(game)
    elder_sect = arena.notice_events(world, world.entity(occurrence), 0, me)[0].data["faction"]
    other = next(f.id for f in world.entities("faction") if f.data["type"] in F.MARTIAL and f.id != elder_sect)
    world.update_data(me, invitations={str(elder_sect): arena.notice_events(world, world.entity(occurrence), 0, me)[0].actors[0]})
    world.relate(me, other, "member_of", 0, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                              "secret": False})  # already sworn to another sect
    assert arena.notice_events(world, world.entity(occurrence), 0, me)[0].data["offer"] == "gift"
    game.perform(Action("accept_invitation", elder_sect))
    assert F.membership(world, me, elder_sect) is None  # "You already belong to..." - no second open sect


def presided_contest(game):
    from systems import founding
    world, town, me = game.world, game.place.id, game.player.id
    youth = founding.make_person(world, "test:champion", town, occupation="apprentice", age=19, realm="third-rate")
    faction = next(f.id for f in world.entities("faction") if f.data["type"] == "school")
    data = {**T.start_data("sect_contest", 8, (1, 1, 1), 0, "First of the contest", 1), "faction": faction,
            "presiding": me, "champion": youth, "finished": True}
    commit(world, sky.start_events(world, "sect_contest", town, world.time - 5 * 4 - 1, data))  # its one day is on
    occurrence = W.index(world)[-1][W.ID]
    world.update_data(occurrence, seen=["announced", "active"])  # already fought: the champion stands
    return occurrence, youth


@pytest.mark.parametrize("how", ["reward_champion", "take_champion"])
def test_presiding_lets_you_reward_the_champion_or_take_them_as_disciple(game, how):
    from engine.actions import Action
    from systems.kin import kin_of
    from systems.purse import silver_of
    world, me = game.world, game.player.id
    world.update_data(me, silver=100)
    occurrence, youth = presided_contest(game)
    turn = game.perform(Action("look"))
    assert Action(how, occurrence) in [c.action for c in turn.all_choices]
    game.perform(Action(how, occurrence))
    if how == "reward_champion":
        assert silver_of(world, me) == 100 - T.CHAMPION_REWARD and silver_of(world, youth) >= T.CHAMPION_REWARD
    else:
        assert (youth, "disciple") in kin_of(world, me)
    assert Action(how, occurrence) not in [c.action for c in game.perform(Action("look")).all_choices]  # once


def test_your_own_sects_contest_is_never_summarised_away(game, monkeypatch):
    import systems.events.sect_contest as sc
    from world.gen.materialize import ensure_town
    world, me = game.world, game.player.id
    monkeypatch.setitem(W.TYPES, "sect_contest", {**W.TYPES["sect_contest"], "every": 1})  # its turn every season
    n = world.time // W.SEASON + 1
    seat = next(s for s in sc.places(world, n, rng_for(1, "p")) if sc.eligible(world, s, n))
    faction = sc._faction_at(world, seat)
    world.relate(me, faction, "member_of", 0, {"role": "disciple", "hall": None, "merit": 0, "status": "member",
                                                "secret": False})
    away = next(t for t in (ensure_town(world, 3, 3, 0), ensure_town(world, -3, -3, 0)) if t != seat)
    world.unrelate(me, "located_in")
    world.relate(me, away, "located_in")  # far from the seat when the season turns
    events = sky.season_events(world, n)
    assert not any(e.kind == "contest_summarized" and e.place == seat for e in events)
    assert any(e.kind == "sky_started" and e.data["type"] == "sect_contest" and e.place == seat for e in events)
