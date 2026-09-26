"""Phase 4g's deferred minors, fixed before merge."""

import pytest

import systems.claimants as C
import systems.encounters as encounters
import systems.regency as R
import systems.succession_crisis as SC
import systems.testament as T
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import founding, halls
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
    still(monkeypatch)  # 4h's intrigue stilled: these test 4g's crises
    monkeypatch.setattr(T, "TRANSMIT_CHANCE", 0.0)
    monkeypatch.setattr(T, "EMERGE_CHANCE", 0.0)
    monkeypatch.setattr(T, "WILL_CHANCE", {"natural": 0.0, "other": 0.0})
    monkeypatch.setattr(T, "CAMP_FIND", 0.0)


def test_a_fallen_claimants_backers_still_count_in_the_total(game, monkeypatch):
    """Their votes are no one's now: undecided, not gone, so a majority is not made easier by a death."""
    world, me = game.world, game.player.id
    sect, seat, keeper, proud, other, occurrence = crisis_at_seat(game)
    game.perform(Action("claim_seat", occurrence.id))
    camps = {keeper: [keeper, other], proud: [proud, 101, 102, 103], me: [me]}
    monkeypatch.setattr(C, "camps", lambda world, crisis, full=True: (
        {k: v for k, v in camps.items() if not world.entity(k).data.get("dead")}, []))
    commit(world, [Event("died", (proud, proud), seat, {"cause": "age", "world": True})])
    monkeypatch.setattr(C, "camps", lambda world, crisis, full=True: (dict(camps), []))
    to_stage(world, occurrence, seat, "active")
    crisis = SC.crisis_of(world.entity(occurrence.id))
    assert crisis["phase"] != "settled" and crisis["trial"] is not None  # 2 of 7 is no majority


def test_a_sitting_leader_is_not_challenged_for_their_own_token_outside_a_crisis(game):
    world, me = game.world, game.player.id
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    world.unrelate(me, "located_in")
    world.relate(me, seat, "located_in")
    [leader] = halls.staff_at(world, sect, seat, roles=("leader",))
    token = T.ensure_token(world, sect)
    T.put(world, token, owner=leader)
    labels = [c.label for c in game.perform(Action("talk", leader)).all_choices]
    assert not any(label.startswith("Challenge them for") for label in labels)
    keeper = halls.staff_at(world, sect, seat, roles=("keeper",))[0]
    T.put(world, token, owner=keeper)  # a token astray: anyone may try for it
    game.perform(Action("farewell"))
    labels = [c.label for c in game.perform(Action("talk", keeper)).all_choices]
    assert any(label.startswith("Challenge them for") for label in labels)


def test_the_regency_check_does_not_read_every_faction(game, monkeypatch):
    world = game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    [keeper] = halls.staff_at(world, sect, seat, roles=("keeper",))
    world.update_data(keeper, age=12)
    world.update_data(sect, regency_for=keeper)
    real = world.entities

    def no_scan(kind):
        assert kind != "faction", "the season's regency check read every faction"
        return real(kind)
    monkeypatch.setattr(world, "entities", no_scan)
    assert R.regency_events(world, 99) == []  # a child still: nothing to do, found without the scan
    world.update_data(keeper, age=16)
    assert R.regency_events(world, 99)  # come of age: the handover, found without the scan


def test_a_death_looks_up_its_memberships_once_for_the_crises(game, monkeypatch):
    world, town = game.world, game.place.id
    person = founding.make_person(world, "test:mortal", town, occupation="wandering swordsman", age=30)
    calls = []
    real = F.memberships

    def counting(world, who):
        import inspect
        calls.append(inspect.stack()[1].frame.f_globals.get("__name__"))
        return real(world, who)
    monkeypatch.setattr(F, "memberships", counting)
    commit(world, [Event("died", (person, person), town, {"cause": "age", "world": True})])
    assert sum(1 for m in calls if m in ("systems.succession_crisis", "systems.testament")) == 1
