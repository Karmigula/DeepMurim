import pytest

import systems.claimants as C
import systems.encounters as encounters
import systems.law as law
import systems.legitimacy as L
import systems.lives as lives
import systems.plots as P
import systems.scheming as S
import systems.succession_crisis as SC
import systems.testament as T
from engine.actions import Action
from engine.game import Game
from narrate.outcomes import SUMMARIES
from systems import factions as F
from systems import founding, halls
from systems.creation import CreationChoice
from tests.intrigue import still
from tests.test_crisis_contest import a_crisis
from tests.test_crisis_play import crisis_at_seat, to_stage
from world.events import commit


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
    monkeypatch.setattr(L, "MANUAL_CHANCE", 0.0)
    monkeypatch.setattr(S, "NPC_FIND", 0.0)


def labels(turn):
    return [c.label for c in turn.all_choices]


def stand_at(world, me, town):
    world.unrelate(me, "located_in")
    world.relate(me, town, "located_in")


def of_type(world, kind):
    return next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == kind)


def test_a_poison_is_bought_from_a_poison_valleys_keeper(game):
    world, me = game.world, game.player.id
    clan = of_type(world, "unorthodox_clan")
    seat = halls.seat_of(world, clan)
    stand_at(world, me, seat)
    [keeper] = halls.staff_at(world, clan, seat, roles=("keeper",))
    world.update_data(me, silver=100)
    assert f"Buy a poison ({S.POISON_PRICE} silver)" in labels(game.perform(Action("talk", keeper)))
    game.perform(Action("buy_poison", keeper))
    assert len(S.poisons_of(world, me)) == 1 and world.entity(me).data["silver"] == 100 - S.POISON_PRICE


def poisoner(game):
    world, me = game.world, game.player.id
    sect = of_type(world, "orthodox_sect")
    seat = halls.seat_of(world, sect)
    stand_at(world, me, seat)
    vial = world.add_entity("treasure", "a vial of black lotus", {"kind": "poison", "value": 50, "used": False})
    world.relate(me, vial, "owns")
    [leader] = halls.staff_at(world, sect, seat, roles=("leader",))
    return sect, seat, leader, vial


def test_a_slipped_poison_kills_in_the_night_and_the_plot_bears_the_players_name(game):
    world, me = game.world, game.player.id
    sect, seat, leader, vial = poisoner(game)
    assert "Slip poison into their tea" in labels(game.perform(Action("talk", leader)))
    game.perform(Action("slip_poison", leader))
    assert world.entity(leader).data.get("dead") and world.entity(vial).data["used"]
    [plot] = P.plots_of(world, sect, ("murder",))
    assert plot.data["plotter"] == me and plot.data["target"] == leader and game.focus is None
    assert world.entity(sect).data["poisoned"] == plot.id  # whispers of poison: the seat is in doubt


def test_an_exposed_poisoner_is_cast_out_hunted_and_named(game):
    world, me = game.world, game.player.id
    sect, seat, leader, vial = poisoner(game)
    world.relate(me, sect, "member_of", 1, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                            "secret": False})
    game.perform(Action("talk", leader))
    game.perform(Action("slip_poison", leader))
    [plot] = P.plots_of(world, sect, ("murder",))
    elder = halls.staff_at(world, sect, seat, roles=("elder",))[0]
    commit(world, P.exposed_events(world, plot, elder, seat))
    assert F.membership(world, me, sect)[1]["status"] == "expelled"
    assert world.facts(predicate="poisoner", subject=me)
    assert law.bounty(world, seat, me) >= 100


def test_a_sworn_follower_can_be_sent_to_spy_and_reports(game):
    world, me = game.world, game.player.id
    sect = of_type(world, "orthodox_sect")
    seat = halls.seat_of(world, sect)
    stand_at(world, me, seat)
    follower = founding.make_person(world, "test:follower", seat, occupation="wandering swordsman", age=25,
                                    sworn_to=me)
    world.update_data(me, silver=200)
    label = f"Send {world.entity(follower).name} to join the {world.entity(sect).name} in secret ({S.SPY_PRICE} silver)"
    assert label in labels(game.perform(Action("look")))
    game.perform(Action("plant_spy", (follower, sect)))
    [plot] = P.plots_of(world, sect, ("spy",))
    assert plot.data["plotter"] == follower and plot.data["patron"] == me
    assert C.role_in(world, follower, sect) == "disciple" and world.entity(follower).data["spy_of"] == me
    import systems.murder as M
    import random
    [leader] = halls.staff_at(world, sect, seat, roles=("leader",))
    elder = halls.staff_at(world, sect, seat, roles=("elder",))[0]
    commit(world, M.murder_events(world, sect, leader, elder, None, seat, random.Random(3)))
    [secret] = P.plots_of(world, sect, ("murder",))
    commit(world, P.season_events(world, lives.current_season(world)))
    assert me in world.entity(secret.id).data["known_by"]  # the spy told you


def test_silver_behind_a_claim_makes_a_puppet_that_remembers_you(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud = a_crisis(game)
    occurrence = SC.live(world, sect)
    world.update_data(me, silver=5000)
    price = S.fund_price(world, sect)
    label = f"Put silver behind {world.entity(keeper).name}'s claim ({price} silver)"
    assert label in labels(game.perform(Action("look")))
    game.perform(Action("fund_claim", (occurrence.id, keeper)))
    [plot] = P.plots_of(world, sect, ("puppet",))
    assert plot.data["plotter"] == me and plot.data["serves"] == keeper and world.entity(me).data["silver"] == 5000 - price
    crisis = SC.crisis_of(world.entity(occurrence.id))
    world.update_data(occurrence.id, data={**crisis, "sways": {str(v): {str(keeper): 5.0} for v in C.voters(world, sect)}})
    to_stage(world, occurrence, seat, "active")
    assert C.role_in(world, keeper, sect) == "leader"
    assert any(m.feeling == "grateful" for m in world.memories(keeper, about=me))


def test_false_evidence_casts_a_rival_out_or_points_back_at_you(game, monkeypatch):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    world.update_data(me, silver=500)
    monkeypatch.setattr(S, "frame_chance", lambda world, player: 0.0)
    game.perform(Action("frame_rival", (occurrence.id, proud)))
    [failed] = P.plots_of(world, sect, ("frame",))
    assert failed.data["failed"] and SC.claimant(SC.crisis_of(world.entity(occurrence.id)), proud) is not None
    assert failed.data["clues"][0]["points_to"] == me
    monkeypatch.setattr(S, "frame_chance", lambda world, player: 1.0)
    game.perform(Action("frame_rival", (occurrence.id, keeper)))
    assert F.membership(world, keeper, sect)[1]["status"] == "expelled"
    assert SC.claimant(SC.crisis_of(world.entity(occurrence.id)), keeper) is None


def test_a_forged_will_names_whom_you_choose(game):
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    world.update_data(me, silver=500)
    game.perform(Action("forge_will", (occurrence.id, proud)))
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert crisis["will"]["state"] == "read" and crisis["will"]["names"] == proud
    [plot] = P.plots_of(world, sect, ("forgery",))
    assert plot.data["plotter"] == me


def test_the_camps_may_find_the_players_hand_in_a_plot(game, monkeypatch):
    monkeypatch.setattr(S, "NPC_FIND", 1.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    world.update_data(me, silver=500)
    game.perform(Action("forge_will", (occurrence.id, proud)))
    [plot] = P.plots_of(world, sect, ("forgery",))
    commit(world, P.found_events(world, plot, "seal", keeper, seat))  # a camp that has found a clue of it
    to_stage(world, occurrence, seat, "announced")
    [plot] = [world.entity(p.id) for p in world.entities("plot") if p.data["type"] == "forgery"]
    assert plot.data["state"] == "exposed" and world.facts(predicate="forger", subject=me)


def test_every_scheme_has_a_journal_line():
    for kind in ("poison_bought", "poison_slipped", "spy_sent", "claim_funded", "frame_paid", "forgery_paid"):
        assert kind in SUMMARIES, kind
