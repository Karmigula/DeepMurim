import pytest

import systems.claimants as C
import systems.encounters as encounters
import systems.lives as lives
import systems.murder as M
import systems.plots as P
import systems.sky as sky
import systems.succession_crisis as SC
import systems.testament as T
import systems.world_clock as clock
from debug.invariants import check_knowledge, check_plots
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.beliefs import known_people
from systems.creation import CreationChoice
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
    monkeypatch.setattr(M, "MURDER_CHANCE", 1.0)
    monkeypatch.setattr(M, "RED_HERRING", 0.0)


def staff(world, sect, seat, role):
    return halls.staff_at(world, sect, seat, roles=(role,))


def poisoned_sect(game):
    """The orthodox sect's master dies 'of age', poisoned by a proud elder; the player stands at the seat."""
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")
    elders = staff(world, sect, seat, "elder")
    world.update_data(elders[0], traits=["proud"])
    world.update_data(elders[1], traits=["kind"], realm="mortal")
    for keeper in staff(world, sect, seat, "keeper"):
        world.update_data(keeper, traits=["kind"])
    [keeper] = staff(world, sect, seat, "keeper")
    commit(world, [Event("named_chief", (keeper,), seat, {"faction": sect, "season": 0})])  # a second claimant
    [leader] = staff(world, sect, seat, "leader")
    real = M.motives
    M.motives = lambda world, faction: [(elders[0], None)]  # the proud elder alone (a war's agent aside)
    try:
        commit(world, [Event("died", (leader, leader), seat, {"cause": "age", "world": True})])
    finally:
        M.motives = real
    [pid] = P.open_plots(world)
    return sect, seat, leader, elders[0], world.entity(pid)


def a_season(game):
    clock.world_tick(game.world)
    game.world.set_time(game.world.time + lives.SEASON)
    clock.run_due(game.world)


def test_a_natural_death_with_a_motive_is_a_poisoning_kept_secret(game):
    world, me = game.world, game.player.id
    sect, seat, leader, proud, plot = poisoned_sect(game)
    d = plot.data
    assert d["type"] == "murder" and d["plotter"] == proud and d["target"] == leader and d["state"] == "open"
    assert [c["kind"] for c in d["clues"]] == ["body", "witness", "motive"]
    assert d["known_by"] == [proud]
    fact = world.fact(d["fact"])
    assert fact.predicate == "poisoned" and {b.knower for b in world.believers(fact.id)} == {proud}
    assert world.entity(sect).data["poisoned"] == plot.id and SC.doubt(world, sect) == "suspicion"
    assert check_plots(world) == []


def test_the_crisis_after_a_poisoning_carries_the_plot(game):
    world = game.world
    sect, seat, leader, proud, plot = poisoned_sect(game)
    a_season(game)
    crisis = SC.crisis_of(SC.live(world, sect))
    assert crisis["cause"] == "suspicion" and crisis["plots"] == [plot.id]
    assert world.entity(sect).data.get("poisoned") is None


def test_no_motive_no_murder(game, monkeypatch):
    world = game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    for person in staff(world, sect, seat, "elder") + staff(world, sect, seat, "keeper"):
        world.update_data(person, traits=["kind"])
    monkeypatch.setattr(M, "motives", lambda world, faction: [])
    [leader] = staff(world, sect, seat, "leader")
    commit(world, [Event("died", (leader, leader), seat, {"cause": "age", "world": True})])
    assert P.open_plots(world) == []


def test_examining_the_body_names_the_poison_and_points_at_the_plotter(game, monkeypatch):
    monkeypatch.setattr(M, "EXAMINE_BASE", 1.0)
    world, me = game.world, game.player.id
    sect, seat, leader, proud, plot = poisoned_sect(game)
    a_season(game)
    occurrence = SC.live(world, sect)
    assert M.examine_block(world, occurrence, me) is None
    commit(world, M.examine_events(world, occurrence, me))
    assert P.suspicions(world, me, sect) == {proud: ["body"]}
    assert proud in known_people(world, me)  # the clue named them
    assert M.examine_block(world, SC.live(world, sect), me) is not None  # once a crisis


def test_the_witness_tells_what_they_saw_once_you_have_reason_to_ask(game):
    world, me = game.world, game.player.id
    sect, seat, leader, proud, plot = poisoned_sect(game)
    witness = next(c["witness"] for c in plot.data["clues"] if c["kind"] == "witness")
    assert M.witness_plot(world, me, witness) is None  # no crisis yet: no whispers, no clue
    a_season(game)
    assert M.witness_plot(world, me, witness).id == plot.id  # the whispers of poison give reason
    commit(world, M.night_events(world, me, witness, seat))
    assert P.suspicions(world, me, sect) == {proud: ["witness"]}


def test_a_suspects_quarters_hold_the_motive(game, monkeypatch):
    monkeypatch.setattr(M, "EXAMINE_BASE", 1.0)
    monkeypatch.setattr(P, "SEARCH_CHANCE", 1.0)
    world, me = game.world, game.player.id
    sect, seat, leader, proud, plot = poisoned_sect(game)
    assert P.search_block(world, me, proud) is not None  # no suspicion, no search
    a_season(game)
    commit(world, M.examine_events(world, SC.live(world, sect), me))
    assert P.search_block(world, me, proud) is None
    commit(world, P.search_events(world, me, proud, seat))
    assert sorted(P.suspicions(world, me, sect)[proud]) == ["body", "motive"]
    assert P.search_block(world, me, proud) == "You searched their quarters this season."


def test_two_clues_expose_the_murderer(game, monkeypatch):
    monkeypatch.setattr(M, "EXAMINE_BASE", 1.0)
    monkeypatch.setattr(P, "SEARCH_CHANCE", 1.0)
    world, me = game.world, game.player.id
    sect, seat, leader, proud, plot = poisoned_sect(game)
    a_season(game)
    occurrence = SC.live(world, sect)
    assert SC.claimant(SC.crisis_of(occurrence), proud) is not None
    commit(world, M.examine_events(world, occurrence, me))
    assert P.accuse_block(world, me, proud, sect) is not None  # one clue is a suspicion, not a case
    commit(world, P.search_events(world, me, proud, seat))
    assert P.accuse_block(world, me, proud, sect) is None
    commit(world, P.accuse_events(world, me, proud, sect, seat))
    assert world.entity(plot.id).data["state"] == "exposed" and plot.id not in P.open_plots(world)
    assert SC.claimant(SC.crisis_of(SC.live(world, sect)), proud) is None  # struck from the claims
    assert F.membership(world, proud, sect)[1]["status"] == "expelled"
    assert world.facts(predicate="murdered", subject=proud)
    elders = [e for e in staff(world, sect, seat, "elder") if e != proud]
    assert all(any(m.feeling == "grateful" for m in world.memories(e, about=me)) for e in elders)
    assert check_plots(world) == []
    assert check_knowledge(world) == []  # the exposer saw it: a witness at no retellings


def test_a_red_herring_can_make_you_accuse_an_innocent(game, monkeypatch):
    monkeypatch.setattr(M, "RED_HERRING", 1.0)
    monkeypatch.setattr(P, "SEARCH_CHANCE", 1.0)
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")
    world.relate(me, sect, "member_of", 2, {"role": "member", "hall": None, "merit": 50, "status": "member",
                                            "secret": False})
    for person in staff(world, sect, seat, "elder"):
        world.update_data(person, traits=["proud"])
    [leader] = staff(world, sect, seat, "leader")
    commit(world, [Event("died", (leader, leader), seat, {"cause": "age", "world": True})])
    [pid] = P.open_plots(world)
    plot = world.entity(pid)
    innocent = next(c["points_to"] for c in plot.data["clues"] if c.get("false"))
    assert innocent != plot.data["plotter"]
    a_season(game)
    witness = next(c["witness"] for c in plot.data["clues"] if c["kind"] == "witness")
    commit(world, M.night_events(world, me, witness, seat))
    commit(world, P.search_events(world, me, innocent, seat))
    assert P.accuse_block(world, me, innocent, sect) is None  # two clues: the case looks sound
    commit(world, P.accuse_events(world, me, innocent, sect, seat))
    assert world.entity(pid).data["state"] == "open"
    assert F.membership(world, me, sect)[1]["merit"] == 50 - P.FALSE_MERIT
    assert any(m.feeling == "wronged" and m.indelible for m in world.memories(innocent, about=me))
    assert check_plots(world) == []


def test_a_secret_leaks_a_witness_can_be_lost_and_a_trail_goes_cold(game, monkeypatch):
    monkeypatch.setattr(P, "LEAK_CHANCE", 1.0)
    monkeypatch.setattr(P, "BURY_CHANCE", 1.0)
    world = game.world
    sect, seat, leader, proud, plot = poisoned_sect(game)
    witness = next(c["witness"] for c in plot.data["clues"] if c["kind"] == "witness")
    n = lives.current_season(world)
    commit(world, P.season_events(world, n))
    plot = world.entity(plot.id)
    assert len(plot.data["known_by"]) == 2  # someone at the seat heard it
    assert world.entity(witness).data.get("vanished") and not world.targets(witness, "located_in")
    assert any(c["kind"] == "missing" for c in plot.data["clues"])
    assert any(c.get("lost") for c in plot.data["clues"] if c["kind"] == "witness")
    commit(world, P.season_events(world, n + P.COLD_SEASONS))
    assert world.entity(plot.id).data["state"] == "cold" and plot.id not in P.open_plots(world)
    assert check_plots(world) == []


def test_an_npc_who_knows_lays_it_before_the_elders(game, monkeypatch):
    monkeypatch.setattr(P, "NPC_EXPOSE", 1.0)
    world = game.world
    sect, seat, leader, proud, plot = poisoned_sect(game)
    a_season(game)
    occurrence = SC.live(world, sect)
    voter = next(v for v in C.voters(world, sect) if v != proud and not world.entity(v).data.get("is_player"))
    P.learn(world, voter, world.entity(plot.id))
    world.set_time(occurrence.data["ends"]["active"])
    sky.observe(world, seat)
    assert world.entity(plot.id).data["state"] == "exposed"
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert proud not in {c["person"] for c in crisis["claimants"]}
    assert check_plots(world) == []
