import random

import pytest

import systems.claimants as C
import systems.encounters as encounters
import systems.frames as R
import systems.lives as lives
import systems.murder as M
import systems.plots as P
import systems.puppets as U
import systems.succession_crisis as SC
import systems.testament as T
from debug.invariants import check_plots
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems.creation import CreationChoice
from tests.test_crisis_play import crisis_at_seat, to_stage
from world.events import commit
from world.gen.materialize import region_of
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
    monkeypatch.setattr(R, "FORGE_CHANCE", 0.0)
    monkeypatch.setattr(R, "FRAME_CHANCE", 0.0)


def cunning_crisis(game, monkeypatch, forge=0.0, frame=0.0):
    """The chief disciple against a cunning elder; at the canvass's start the elder may forge or frame."""
    monkeypatch.setattr(R, "FORGE_CHANCE", forge)
    monkeypatch.setattr(R, "FRAME_CHANCE", frame)
    world = game.world
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    world.update_data(proud, traits=["cunning"])
    to_stage(world, occurrence, seat, "announced")
    return sect, seat, keeper, proud, occurrence


def test_a_cunning_claimant_forges_the_will(game, monkeypatch):
    world = game.world
    sect, seat, keeper, forger, occurrence = cunning_crisis(game, monkeypatch, forge=1.0)
    crisis = SC.crisis_of(world.entity(occurrence.id))
    [plot] = P.plots_of(world, sect, ("forgery",))
    assert crisis["will"]["state"] == "read" and crisis["will"]["names"] == forger
    assert crisis["will"]["forged"] == plot.id and plot.id in crisis["plots"]
    assert "will" in C.proofs(world, crisis, SC.claimant(crisis, forger))
    assert check_plots(world) == []


def test_the_seal_and_the_scribe_expose_a_forgery(game, monkeypatch):
    monkeypatch.setattr(R, "seal_chance", lambda world, player: 1.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, forger, occurrence = cunning_crisis(game, monkeypatch, forge=1.0)
    [plot] = P.plots_of(world, sect, ("forgery",))
    occurrence = world.entity(occurrence.id)
    assert R.examine_will_block(world, occurrence, me) is None
    commit(world, R.examine_will_events(world, occurrence, me))
    assert R.examine_will_block(world, world.entity(occurrence.id), me) is not None  # once a crisis
    scribe = next(c["witness"] for c in plot.data["clues"] if c["kind"] == "scribe")
    commit(world, R.asked_events(world, me, scribe, seat, "scribe"))
    commit(world, P.accuse_events(world, me, forger, sect, seat))
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert crisis["will"]["state"] == "forged" and SC.claimant(crisis, forger) is None
    assert check_plots(world) == []


def test_a_framed_claimant_is_cast_out_and_waits_in_exile(game, monkeypatch):
    world = game.world
    sect, seat, keeper, framer, occurrence = cunning_crisis(game, monkeypatch, frame=1.0)
    [plot] = P.plots_of(world, sect, ("frame",))
    framed = plot.data["target"]
    assert framed == keeper and plot.data["plotter"] == framer
    assert F.membership(world, framed, sect)[1]["status"] == "expelled"
    assert SC.claimant(SC.crisis_of(world.entity(occurrence.id)), framed) is None
    home, there = region_of(world, seat), region_of(world, world.targets(framed, "located_in")[0])
    assert max(abs(home.data["x"] - there.data["x"]), abs(home.data["y"] - there.data["y"])) >= R.EXILE_REACH[0]
    exile = world.entity(framed).data["framed"]
    assert exile["plot"] == plot.id and exile["returns_at"] - exile["since"] >= R.RETURN_SEASONS[0]
    assert framed in R.exiles(world)
    [crime] = [f for f in world.facts(subject=framed) if f.predicate in R.CRIMES]
    assert not crime.is_true
    assert check_plots(world) == []


def test_the_false_witness_can_be_made_to_tell(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat, keeper, framer, occurrence = cunning_crisis(game, monkeypatch, frame=1.0)
    [plot] = P.plots_of(world, sect, ("frame",))
    witness = next(c["witness"] for c in plot.data["clues"] if c["kind"] == "false_witness")
    commit(world, R.asked_events(world, me, witness, seat, "false_witness"))
    assert P.suspicions(world, me, sect) == {framer: ["false_witness"]}


def test_the_framed_come_home_to_a_live_crisis_or_start_their_own(game, monkeypatch):
    world = game.world
    sect, seat, keeper, framer, occurrence = cunning_crisis(game, monkeypatch, frame=1.0)
    [plot] = P.plots_of(world, sect, ("frame",))
    n = lives.current_season(world)
    world.update_data(keeper, framed={**world.entity(keeper).data["framed"], "returns_at": n})
    commit(world, R.returns_due(world, n))
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert {"person": keeper, "kind": "returned", "plot": plot.id} in crisis["claimants"]
    assert world.targets(keeper, "located_in") == [seat] and keeper not in R.exiles(world)
    plot = world.entity(plot.id)
    assert keeper in plot.data["known_by"]  # they know who framed them, and bring the planted evidence
    assert any(c["kind"] == "planted" and keeper in c["found_by"] for c in plot.data["clues"])


def test_an_heir_whose_frame_was_exposed_returns_with_the_truth(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat, keeper, framer, occurrence = cunning_crisis(game, monkeypatch, frame=1.0)
    [plot] = P.plots_of(world, sect, ("frame",))
    commit(world, P.exposed_events(world, plot, me, seat))
    crisis = SC.crisis_of(world.entity(occurrence.id))
    world.update_data(occurrence.id, data={**crisis, "sways": {str(v): {str(framer): 5.0}
                                                               for v in C.voters(world, sect)}})
    to_stage(world, occurrence, seat, "active")  # the crisis is settled while they are away
    world.set_time(world.entity(occurrence.id).data["over_at"] + lives.SEASON)  # and a season on
    n = lives.current_season(world)
    world.update_data(keeper, framed={**world.entity(keeper).data["framed"], "returns_at": n})
    commit(world, R.returns_due(world, n))
    live = SC.live(world, sect)
    assert live is not None and SC.crisis_of(live)["cause"] == "return"
    crisis = SC.crisis_of(live)
    returned = SC.claimant(crisis, keeper)
    assert returned["kind"] == "returned" and "truth" in C.proofs(world, crisis, returned)


def test_a_framed_player_may_come_back_to_demand_the_seat(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("claim_seat", occurrence.id))
    world.update_data(proud, traits=["cunning"])
    commit(world, R.frame_events(world, world.entity(occurrence.id), proud, me, "frame:test", random.Random(1)))
    assert F.membership(world, me, sect)[1]["status"] == "expelled"
    assert world.targets(me, "located_in") == [seat]  # the player is not carried off: they walk out themselves
    assert R.player_return_block(world, me, seat) == "It is too soon: the elders' anger is fresh."
    since = world.entity(me).data["framed"]["since"]
    world.update_data(me, framed={**world.entity(me).data["framed"], "since": since - R.PLAYER_RETURN})
    assert R.player_return_block(world, me, seat) is None
