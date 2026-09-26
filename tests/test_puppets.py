import pytest

import systems.claimants as C
import systems.encounters as encounters
import systems.lives as lives
import systems.murder as M
import systems.plots as P
import systems.puppets as U
import systems.succession_crisis as SC
import systems.testament as T
import systems.wars as wars
import systems.world_clock as clock
from debug.invariants import check_plots
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from tests.test_crisis_play import crisis_at_seat, to_stage
from world.events import Event, commit
from tests.intrigue import still


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


@pytest.fixture(autouse=True)
def calm(monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
    still(monkeypatch)  # every intrigue stilled; each test asks for its own
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)
    monkeypatch.setattr(T, "EMERGE_CHANCE", 0.0)
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 0.0, "other": 0.0})
    monkeypatch.setattr(T, "CAMP_FIND", 0.0)
    monkeypatch.setattr(M, "MURDER_CHANCE", 0.0)
    monkeypatch.setattr(U, "PUPPET_CHANCE", 0.0)


def the_sects(world):
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    cult = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "demonic_cult")
    world.update_data(cult, home=list(world.entity(sect).data["home"]))  # within reach
    world.relate(sect, cult, "stance", -0.8)
    world.relate(cult, sect, "stance", -0.8)
    halls.seat_of(world, cult)
    return sect, cult


def a_puppet(game, monkeypatch):
    monkeypatch.setattr(U, "PUPPET_CHANCE", 1.0)
    world = game.world
    sect, cult = the_sects(world)
    found = crisis_at_seat(game)
    [plot] = P.plots_of(world, sect, ("puppet",))
    return sect, cult, found, plot


def test_a_hostile_sect_within_reach_backs_a_puppet_with_a_fighter(game, monkeypatch):
    world = game.world
    sect, cult, (_, seat, keeper, proud, other, occurrence), plot = a_puppet(game, monkeypatch)
    d = plot.data
    assert d["patron"] == cult and d["serves"] in (keeper, proud) and d["occurrence"] == occurrence.id
    envoy = d["plotter"]
    assert world.targets(envoy, "located_in") == [seat] and F.membership(world, envoy, cult) is not None
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert plot.id in crisis["plots"]
    assert crisis["champions"][str(d["serves"])] == d["lent"] and C.role_in(world, d["lent"], cult) == "elder"
    assert check_plots(world) == []


def test_the_puppets_silver_sways_the_voters_and_a_gifted_voter_can_be_asked(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, cult, (_, seat, keeper, proud, other, occurrence), plot = a_puppet(game, monkeypatch)
    to_stage(world, occurrence, seat, "announced")  # the canvass begins: the silver is spent
    plot = world.entity(plot.id)
    crisis = SC.crisis_of(world.entity(occurrence.id))
    puppet = str(plot.data["serves"])
    assert plot.data["gifted"] and all(crisis["sways"][str(v)][puppet] >= U.GIFT for v in plot.data["gifted"])
    voter = plot.data["gifted"][0]
    commit(world, U.asked_events(world, me, voter, seat, "silver"))
    commit(world, U.asked_events(world, me, plot.data["plotter"], seat, "envoy"))
    envoy = plot.data["plotter"]
    assert sorted(P.suspicions(world, me, sect)[envoy]) == ["envoy", "silver"]
    commit(world, P.accuse_events(world, me, envoy, sect, seat))
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert world.entity(plot.id).data["state"] == "exposed"
    assert all(crisis["sways"][str(v)][puppet] <= U.GIFT + U.EXPOSED_LEAN + 1e-9 for v in plot.data["gifted"])
    assert F.stance(world, sect, cult) == pytest.approx(-1.0)  # -0.8 - 0.3, bounded
    assert check_plots(world) == []


def test_a_puppet_who_wins_puts_the_sect_in_the_patrons_pocket(game, monkeypatch):
    world = game.world
    sect, cult, (_, seat, keeper, proud, other, occurrence), plot = a_puppet(game, monkeypatch)
    puppet = plot.data["serves"]
    crisis = SC.crisis_of(world.entity(occurrence.id))
    world.update_data(occurrence.id, data={**crisis, "sways": {str(v): {str(puppet): 5.0} for v in C.voters(world, sect)}})
    to_stage(world, occurrence, seat, "active")
    assert C.role_in(world, puppet, sect) == "leader"
    assert F.stance(world, sect, cult) == U.POCKET_STANCE and U.in_pocket(world, sect, cult)
    world.relate(sect, cult, "stance", -1.0)
    world.relate(cult, sect, "stance", -1.0)
    monkeypatch.setattr(wars, "WAR_CHANCE", 1.0)
    clashes = [e for e in wars.clash_events(world, 99) if e.kind == "clash" and set(e.actors) == {sect, cult}]
    assert clashes == []  # no war on the patron while its puppet leads


def spy_in(game, monkeypatch):
    monkeypatch.setattr(U, "SPY_CHANCE", 1.0)
    world = game.world
    sect, cult = the_sects(world)
    commit(world, U.planting_events(world, 4))
    [plot] = P.plots_of(world, sect, ("spy",))
    return sect, cult, plot


def test_a_cult_plants_a_spy_among_a_hostile_sects_keepers_and_disciples(game, monkeypatch):
    world = game.world
    sect, cult, plot = spy_in(game, monkeypatch)
    spy = plot.data["plotter"]
    assert world.entity(spy).data["spy_of"] == cult and C.role_in(world, spy, sect) in ("keeper", "disciple")
    assert U.planting_events(world, 5) == []  # once a year
    assert (spy, cult) in M.motives(world, sect)  # a spy is a motive for murder
    assert check_plots(world) == []


def test_a_spys_year_may_steal_an_art_for_the_cult(game, monkeypatch):
    monkeypatch.setattr(U, "THEFT_CHANCE", 1.0)
    world = game.world
    sect, cult, plot = spy_in(game, monkeypatch)
    world.update_data(sect, arts=[4242])
    commit(world, P.season_events(world, 8))
    assert 4242 in world.entity(cult).data["arts"]


def test_a_spy_exposed_is_cast_out(game, monkeypatch):
    monkeypatch.setattr(P, "SEARCH_CHANCE", 1.0)
    world, me = game.world, game.player.id
    sect, cult, plot = spy_in(game, monkeypatch)
    spy = plot.data["plotter"]
    seat = world.entity(sect).data["seat"]
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")
    witness = next(c["witness"] for c in plot.data["clues"] if c["kind"] == "night")
    commit(world, P.found_events(world, plot, "night", me, seat))  # the witness saw them outside the walls
    world.unrelate(spy, "located_in")
    world.relate(spy, seat, "located_in")
    commit(world, P.search_events(world, me, spy, seat))
    commit(world, P.accuse_events(world, me, spy, sect, seat))
    assert F.membership(world, spy, sect)[1]["status"] == "spy_exposed" and not world.entity(spy).data.get("spy_of")
    assert F.stance(world, sect, cult) == pytest.approx(-1.0)
    assert world.facts(predicate="spy_exposed", subject=spy)
    assert witness is not None and check_plots(world) == []


def test_a_cult_spy_declares_for_the_cults_puppet(game, monkeypatch):
    world = game.world
    sect, cult, plot = spy_in(game, monkeypatch)
    spy = plot.data["plotter"]
    monkeypatch.setattr(U, "PUPPET_CHANCE", 1.0)
    monkeypatch.setattr(U, "patrons", lambda world, faction: [cult])
    _, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    [puppet_plot] = P.plots_of(world, sect, ("puppet",))
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert crisis["declared"][str(spy)] == puppet_plot.data["serves"]
