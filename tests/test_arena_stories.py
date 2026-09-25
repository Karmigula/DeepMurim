import pytest

import systems.agendas as agendas
import systems.arena as arena
import systems.encounters as encounters
import systems.sky as sky
import systems.tournaments as T
import systems.world_events as W
from engine.actions import Action
from engine.game import Game
from systems import factions as F
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


def drawn_assembly(game, registered=()):
    import systems.events.grand_assembly as ga
    world, town = game.world, game.place.id
    commit(world, sky.start_events(world, "grand_assembly", town, world.time,
                                   {**ga.start_data(world, town, 10, rng_for(1, "a")), "registered": list(registered)}))
    occurrence = W.index(world)[-1][W.ID]
    world.set_time(T.day_start(world.entity(occurrence), 1))
    sky.observe(world, town)
    return occurrence


def test_watching_settles_a_bout_before_your_eyes(game):
    world, me = game.world, game.player.id
    occurrence = drawn_assembly(game)
    r, i, m = arena.watchable(world, occurrence, me)
    turn = game.perform(Action("watch", occurrence))
    assert world.entity(occurrence).data["data"]["rounds"][r][i]["how"] == "sim"
    assert {m["a"], m["b"]} <= set(world.acquaintances(me))
    assert world.entity(me).data.get("fragments") and any("watch" in t.lower() for t, _ in turn.lines)


def test_you_cannot_watch_another_days_bouts(game):
    world, me = game.world, game.player.id
    occurrence = drawn_assembly(game)
    world.set_time(T.day_start(world.entity(occurrence), 2))
    assert arena.watchable(world, occurrence, me) is None  # day 2 of the Assembly has no bouts (rounds fall on 1, 3, 5, 7, 8)


def test_an_elder_invites_a_winning_player(game, monkeypatch):
    monkeypatch.setattr(arena, "NOTICE_BASE", 5.0)
    world, me, town = game.world, game.player.id, game.place.id
    occurrence = drawn_assembly(game)
    events = arena.notice_events(world, world.entity(occurrence), 0, me)
    assert events and events[0].data["offer"] == "invite"
    commit(world, events)
    faction = events[0].data["faction"]
    turn = game.perform(Action("look"))
    assert Action("accept_invitation", faction) in [c.action for c in turn.all_choices]
    game.perform(Action("accept_invitation", faction))
    assert F.membership(world, me, faction) is not None


def test_a_members_notice_is_a_gift(game, monkeypatch):
    monkeypatch.setattr(arena, "NOTICE_BASE", 5.0)
    world, me = game.world, game.player.id
    occurrence = drawn_assembly(game)
    faction = arena.notice_events(world, world.entity(occurrence), 0, me)[0].data["faction"]
    world.relate(me, faction, "member_of", 0, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                                "secret": False})
    silver = silver_of(world, me)
    commit(world, arena.notice_events(world, world.entity(occurrence), 0, me))
    assert silver_of(world, me) > silver


def test_a_noticed_npc_joins_the_sect(game, monkeypatch):
    monkeypatch.setattr(arena, "NOTICE_BASE", 5.0)
    world, town = game.world, game.place.id
    wanderer = founding.make_person(world, "test:wanderer", town, occupation="wandering swordsman", age=25,
                                    realm="second-rate")
    occurrence = drawn_assembly(game)
    events = arena.notice_events(world, world.entity(occurrence), 0, wanderer)
    commit(world, events)
    assert F.membership(world, wanderer, events[0].data["faction"])[1]["role"] == "disciple"


def test_losers_remember_and_the_proud_want_revenge(game, monkeypatch):
    monkeypatch.setattr(arena, "GRUDGE_CHANCE", 1.0)
    world, town = game.world, game.place.id
    occurrence = drawn_assembly(game)
    world.set_time(T.day_start(world.entity(occurrence), 2))
    sky.observe(world, town)
    t = world.entity(occurrence).data["data"]
    losers = [(m["b"] if m["winner"] == m["a"] else m["a"], m["winner"]) for m in t["rounds"][0] if m["how"] == "sim"]
    remembered = [(l, w) for l, w in losers if any(mem.event.actors and mem.event.actors[0] == w
                                                  for mem in world.memories(l))]
    assert remembered
    proud = [(l, w) for l, w in losers if {"proud", "hot-tempered"} & set(world.entity(l).data.get("traits", []))]
    for loser, winner in proud:
        found = agendas.grudge(world, loser, world.time // W.SEASON)
        assert found is not None and found[0] == winner
