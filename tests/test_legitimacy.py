import pytest

import systems.claimants as C
import systems.crisis_play as CP
import systems.encounters as encounters
import systems.legitimacy as L
import systems.succession_crisis as SC
import systems.testament as T
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import founding, halls
from systems.creation import CreationChoice
from systems.techniques import GRADE_MULT
from tests.test_crisis_play import crisis_at_seat, to_stage
from tests.intrigue import still
from world.events import Event, commit


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


def staff(world, sect, seat, role):
    return halls.staff_at(world, sect, seat, roles=(role,))


def test_the_supreme_art_is_made_once_and_taught_to_a_chief_disciple_of_a_years_standing(game):
    world = game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    art = L.supreme_art(world, sect)
    assert L.supreme_art(world, sect) == art and world.entity(art).data["grade"] == len(GRADE_MULT)
    [keeper] = staff(world, sect, seat, "keeper")
    commit(world, [Event("named_chief", (keeper,), seat, {"faction": sect, "season": 0})])
    since = world.entity(sect).data["heir_since"]
    n = since + L.HEIR_LEARNS + (4 - (since + L.HEIR_LEARNS) % 4) % 4
    commit(world, L.teaching_events(world, n))
    assert L.art_known(world, keeper, sect) == L.ART_KNOWN
    crisis = {"faction": sect, "claimants": [{"person": keeper, "kind": "chief"}], "leader": None}
    assert "supreme_art" in C.proofs(world, crisis, crisis["claimants"][0])


def test_a_manual_of_the_art_may_lie_in_the_late_masters_rooms(game, monkeypatch):
    monkeypatch.setattr(L, "MANUAL_CHANCE", 1.0)
    monkeypatch.setattr(L, "MANUAL_FIND", 1.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    manual = world.entity(sect).data["art_manual"]
    assert world.sources(manual, "owns") == [sect]  # the sect holds it until someone finds it
    to_stage(world, occurrence, seat, "announced")
    commit(world, CP.search_events(world, world.entity(occurrence.id), me))
    assert world.sources(manual, "owns") == [me] and world.entity(sect).data["art_manual"] is None


def test_passing_the_founders_test_takes_the_seat(game, monkeypatch):
    monkeypatch.setattr(L, "test_chance", lambda world, person: 1.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("claim_seat", occurrence.id))
    occurrence = world.entity(occurrence.id)
    assert L.test_block(world, occurrence, me) is None
    commit(world, L.test_events(world, occurrence, me))
    assert C.role_in(world, me, sect) == "leader"
    assert SC.crisis_of(world.entity(occurrence.id))["outcome"]["how"] == "founder"


def test_failing_the_founders_test_costs_the_claim_and_can_cost_a_life(game, monkeypatch):
    monkeypatch.setattr(L, "test_chance", lambda world, person: 0.0)
    monkeypatch.setattr(L, "TEST_DEATH", 0.0)
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("claim_seat", occurrence.id))
    commit(world, L.test_events(world, world.entity(occurrence.id), me))
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert SC.claimant(crisis, me) is None and me in crisis["tested"]
    from systems.bodies import load_body
    assert any(i.cause == "the founder's test" for i in load_body(world, me).injuries)
    monkeypatch.setattr(L, "TEST_DEATH", 1.0)
    before = world.entity(proud).data["realm"]
    commit(world, L.test_events(world, world.entity(occurrence.id), proud))
    assert world.entity(proud).data.get("dead")
    assert before


def test_an_ambitious_npc_may_try_the_test_in_the_mourning(game, monkeypatch):
    monkeypatch.setattr(L, "NPC_TRY", 1.0)
    monkeypatch.setattr(L, "test_chance", lambda world, person: 1.0)
    world = game.world
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    [leader] = staff(world, sect, seat, "leader")  # the heralds' day came with the crisis: the mourning's work
    assert C.ambitious(world, leader) and world.entity(sect).data["history"][-1]["how"] == "founder"


def test_a_claimant_may_marry_into_the_late_masters_line(game, monkeypatch):
    monkeypatch.setattr(L, "MARRY_CHANCE", 1.0)
    world = game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    [leader] = staff(world, sect, seat, "leader")
    daughter = founding.make_person(world, "test:daughter", seat, occupation="wandering swordsman", age=22)
    world.relate(leader, daughter, "kin_of", 0, {"role": "child"})
    world.relate(daughter, leader, "kin_of", 0, {"role": "parent"})
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    import systems.sky as sky
    sky.observe(world, seat)
    crisis = SC.crisis_of(world.entity(occurrence.id))
    wed = [c for c in crisis["claimants"] if L.married_line(world, crisis, c["person"])]
    assert wed and "married_line" in C.proofs(world, crisis, wed[0])


def test_an_arbiter_may_rule_where_there_is_no_majority(game, monkeypatch):
    monkeypatch.setattr(L, "ARBITER_CHANCE", 1.0)
    monkeypatch.setattr(L, "DEFY_CHANCE", 0.0)
    world = game.world
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    monkeypatch.setattr(C, "camps", lambda world, crisis, full=True: (
        {c["person"]: [c["person"]] for c in crisis["claimants"]}, [1, 2, 3]))
    to_stage(world, occurrence, seat, "active")
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert crisis["outcome"]["how"] == "arbiter" and world.chronicle_of_kind("arbitrated")


def test_a_proud_loser_may_defy_the_arbiter(game, monkeypatch):
    monkeypatch.setattr(L, "ARBITER_CHANCE", 1.0)
    monkeypatch.setattr(L, "DEFY_CHANCE", 1.0)
    monkeypatch.setattr(L, "verdict", lambda world, crisis, standing: next(
        c["person"] for c in standing if "proud" not in world.entity(c["person"]).data.get("traits", ())))
    world = game.world
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    monkeypatch.setattr(C, "camps", lambda world, crisis, full=True: (
        {c["person"]: [c["person"]] for c in crisis["claimants"]}, [1, 2, 3]))
    to_stage(world, occurrence, seat, "active")
    assert SC.crisis_of(world.entity(occurrence.id))["phase"] == "strife"
    assert world.facts(predicate="defied_arbiter", subject=proud)


def test_a_master_with_no_chief_disciple_may_name_an_outsider(game, monkeypatch):
    monkeypatch.setattr(L, "OUTSIDER_CHANCE", 1.0)
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")
    [leader] = staff(world, sect, seat, "leader")
    wanderer = founding.make_person(world, "test:wanderer", seat, occupation="wandering swordsman", age=40,
                                    realm=world.entity(leader).data["realm"])
    commit(world, [Event("died", (leader, leader), seat, {"cause": "killed", "world": True})])
    assert world.entity(sect).data["outsider"] == wanderer
    import systems.lives as lives
    import systems.world_clock as clock
    clock.world_tick(world)
    world.set_time(world.time + lives.SEASON)
    clock.run_due(world)
    crisis = SC.crisis_of(SC.live(world, sect))
    outsider = SC.claimant(crisis, wanderer)
    assert outsider == {"person": wanderer, "kind": "outsider"}
    voter = next(v for v in C.voters(world, sect) if v != wanderer and not world.entity(v).data.get("is_player"))
    assert C.lean(world, crisis, voter, outsider, full=False) < C.lean(
        world, crisis, voter, {"person": wanderer, "kind": "elder"}, full=False)
