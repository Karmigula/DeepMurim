import pytest

import systems.arena as arena
import systems.encounters as encounters
import systems.intrigue as intrigue
import systems.sky as sky
import systems.tournaments as T
import systems.wagers as wagers
import systems.world_events as W
from debug.invariants import check_tournaments
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems.creation import CreationChoice
from systems.purse import silver_of
from systems.reputation import reputation
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


def to_day(game, occurrence, k):
    game.world.set_time(T.day_start(game.world.entity(occurrence), k))
    sky.observe(game.world, game.place.id)


def drawn(game, monkeypatch, plot, **knobs):
    """An Assembly in the player's town, drawn on day 1, carrying this intervention."""
    import systems.events.grand_assembly as ga
    monkeypatch.setitem(intrigue.CHANCES, "grand_assembly", ((plot, 1.0),))
    for name, value in knobs.items():
        monkeypatch.setattr(intrigue, name, value)
    world, town = game.world, game.place.id
    commit(world, sky.start_events(world, "grand_assembly", town, world.time,
                                   ga.start_data(world, town, 10, rng_for(1, "a"))))
    occurrence = W.index(world)[-1][W.ID]
    to_day(game, occurrence, 1)
    return occurrence


def plot_of(world, occurrence):
    return world.entity(occurrence).data["data"]["intrigue"]


def heard(world, town, predicate):
    return [f for _, f in world.known_facts(town) if f.predicate == predicate]


def test_a_draw_carries_one_seeded_intervention_at_most(game, monkeypatch):
    world = game.world
    occurrence = drawn(game, monkeypatch, "fixed")
    t = world.entity(occurrence).data["data"]
    first = intrigue.plot(world, world.entity(occurrence), t["rounds"], t["entrants"])
    assert first["kind"] == "fixed" and first == intrigue.plot(world, world.entity(occurrence), t["rounds"], t["entrants"])
    monkeypatch.setitem(intrigue.CHANCES, "grand_assembly", ())
    assert intrigue.plot(world, world.entity(occurrence), t["rounds"], t["entrants"]) is None


def test_a_fix_is_a_secret_from_the_draw(game, monkeypatch):
    world = game.world
    occurrence = drawn(game, monkeypatch, "fixed")
    p = plot_of(world, occurrence)
    m = world.entity(occurrence).data["data"]["rounds"][0][p["match"]]
    assert (p["victim"], p["against"]) == (m["a"], m["b"])  # the favourite is the one got at
    assert world.fact(p["fact"]).predicate == "fixed" and world.believers(p["fact"]) == []


@pytest.mark.parametrize("seen", [True, False])
def test_the_fixed_fighter_fights_weakened(game, monkeypatch, seen):
    world, me = game.world, game.player.id
    occurrence = drawn(game, monkeypatch, "fixed", FIX_FACTOR=0.0, RUMOUR_CHANCE=0.0)
    p = plot_of(world, occurrence)
    if not seen:
        world.unrelate(me, "located_in")  # far away, bouts are decided by realm (level of detail)
    world.set_time(T.day_start(world.entity(occurrence), 2))
    T.resolve(world, occurrence)
    m = world.entity(occurrence).data["data"]["rounds"][0][p["match"]]
    assert m["how"] == "sim" and m["winner"] == p["against"]


def test_watching_the_fixed_bout_reveals_it(game, monkeypatch):
    world, me = game.world, game.player.id
    occurrence = drawn(game, monkeypatch, "fixed", RUMOUR_CHANCE=0.0)
    p = plot_of(world, occurrence)
    for _ in range(16):
        if intrigue.knows(world, me, p["fact"]) or arena.watchable(world, occurrence, me) is None:
            break
        commit(world, arena.watch_events(world, occurrence, me))
    assert intrigue.knows(world, me, p["fact"])
    assert Action("expose_fix", occurrence) in [c.action for c in game.perform(Action("look")).all_choices]


def test_the_bookmaker_may_let_a_fix_slip(game, monkeypatch):
    world, me = game.world, game.player.id
    occurrence = drawn(game, monkeypatch, "fixed", ASK_BASE=1.0)
    p = plot_of(world, occurrence)
    world.update_data(me, silver=500)
    turn = game.perform(Action("bookmaker", occurrence))
    assert Action("ask_bookmaker", occurrence) in [c.action for c in turn.all_choices]
    game.perform(Action("ask_bookmaker", occurrence))
    assert intrigue.knows(world, me, p["fact"])
    assert intrigue.ask_block(world, occurrence, me) is not None  # once a tournament


def test_a_straight_tournament_gives_the_bookmaker_nothing_to_tell(game, monkeypatch):
    world, me = game.world, game.player.id
    occurrence = drawn(game, monkeypatch, "raid", ASK_BASE=1.0)
    assert intrigue.ask_events(world, occurrence, me)[0].data["learned"] is False


def test_exposing_a_fix_spreads_it_and_brings_renown(game, monkeypatch):
    world, me, town = game.world, game.player.id, game.place.id
    occurrence = drawn(game, monkeypatch, "fixed", ASK_BASE=1.0, RUMOUR_CHANCE=0.0)
    p = plot_of(world, occurrence)
    commit(world, intrigue.ask_events(world, occurrence, me))
    before = reputation(world, town, me).renown
    game.perform(Action("expose_fix", occurrence))
    assert town in {b.knower for b in world.believers(p["fact"])}
    assert reputation(world, town, me).renown > before
    assert plot_of(world, occurrence)["exposed"] and intrigue.exposable(world, me) == []


def test_a_fix_may_come_out_on_its_own(game, monkeypatch):
    world, town = game.world, game.place.id
    occurrence = drawn(game, monkeypatch, "fixed", RUMOUR_CHANCE=1.0)
    p = plot_of(world, occurrence)
    to_day(game, occurrence, 2)
    assert town in {b.knower for b in world.believers(p["fact"])}


def test_a_raid_breaks_up_the_final_and_it_is_fought_again(game, monkeypatch):
    world, town = game.world, game.place.id
    occurrence = drawn(game, monkeypatch, "raid", RAID_DEATH=0.0)
    to_day(game, occurrence, 8)
    final = world.entity(occurrence).data["data"]["rounds"][-1][0]
    assert plot_of(world, occurrence)["done"] and final["how"] is None and final["day"] == 9
    assert heard(world, town, "raided")
    to_day(game, occurrence, 10)
    t = world.entity(occurrence).data["data"]
    assert t["finished"] and t["champion"] is not None and t["champion"] == t["rounds"][-1][0]["winner"]
    assert check_tournaments(world) == []


def test_a_finalist_slain_in_a_raid_voids_the_final(game, monkeypatch):
    world = game.world
    occurrence = drawn(game, monkeypatch, "raid", RAID_DEATH=1.0)
    to_day(game, occurrence, 8)
    t = world.entity(occurrence).data["data"]
    final = t["rounds"][-1][0]
    assert final["how"] == "void" and t["finished"] and t["champion"] is None
    assert all(not T.alive(world, p) for p in (final["a"], final["b"]))
    assert check_tournaments(world) == []


def test_you_may_join_the_defence(game, monkeypatch):
    world, me = game.world, game.player.id
    occurrence = drawn(game, monkeypatch, "raid", RAID_DEATH=0.0)
    to_day(game, occurrence, 8)
    cultist = intrigue.defence_open(world, occurrence, me)
    assert cultist is not None
    assert Action("defend", occurrence) in [c.action for c in game.perform(Action("look")).all_choices]
    game.perform(Action("defend", occurrence))
    assert game.combat is not None and game.combat.opponent == cultist
    commit(world, intrigue.defended_events(world, occurrence, me, cultist, True))
    assert intrigue.defence_open(world, occurrence, me) is None
    assert heard(world, game.place.id, "defended")


def test_a_favourite_vanishes_the_night_before_their_round(game, monkeypatch):
    world, town = game.world, game.place.id
    occurrence = drawn(game, monkeypatch, "vanished")
    p = plot_of(world, occurrence)
    t = world.entity(occurrence).data["data"]
    world.update_data(occurrence, data={**t, "intrigue": {**p, "round": 1}})
    first = next(m for m in t["rounds"][0] if p["victim"] in (m["a"], m["b"]))
    rival = first["b"] if first["a"] == p["victim"] else first["a"]
    world.update_data(rival, dead=True)  # the favourite walks over into round 2
    to_day(game, occurrence, 2)
    victim = world.entity(p["victim"])
    assert victim.data.get("vanished") and not world.targets(victim.id, "located_in")
    assert all(d.get("status") == "missing" for _, _, d in F.memberships(world, victim.id))
    to_day(game, occurrence, 4)
    m = next(m for m in world.entity(occurrence).data["data"]["rounds"][1] if p["victim"] in (m["a"], m["b"]))
    assert m["how"] == "walkover" and m["winner"] != p["victim"]
    assert heard(world, town, "vanished")


def test_bets_on_a_void_match_are_returned(game, monkeypatch):
    world, me = game.world, game.player.id
    occurrence = drawn(game, monkeypatch, "raid")
    world.update_data(me, silver=500)
    r, i, m = wagers.open_matches(world, occurrence)[0]
    commit(world, wagers.bet_events(world, occurrence, r, i, m["a"], 50, me))
    commit(world, [T.match_event(world.entity(occurrence), r, i, None, None, "void", 1)])
    assert silver_of(world, me) == 500
