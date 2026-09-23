import pytest

import systems.encounters as encounters
import systems.founding as founding
import systems.land as land
import systems.sect as sect_mod
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from systems.realms import REALMS, realm_index
from systems.techniques import known_arts, martial_arts
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


def found_sect(game, path="righteous"):
    """Found a sect in a town with a magistrate, with three followers, skipping the menus."""
    from tests.test_land import buyable_town
    world, me = game.world, game.player.id
    town = buyable_town(game)
    halls.settle_town(world, town)
    world.unrelate(me, "located_in")
    world.relate(me, town, "located_in")
    commit(world, land.claim_events(me, town))
    for i in range(3):
        follower = founding.make_person(world, f"test:follower:{i}", town)
        commit(world, [Event("sworn", (me, follower), town, {"accepted": True})])
    body = load_body(world, me)
    body.realm = realm_index("second-rate")
    body.energy_years = max(body.energy_years, REALMS[body.realm].threshold)
    save_body(world, me, body)
    world.update_data(me, silver=500)
    choice = {"name": "Test Pine Sect", "path": path, "taboos": ["never_rob", "never_kill_unarmed"],
              "trial": "spar", "ranks": "orthodox"}
    game._commit(founding.founded_events(world, me, land.magistrate_of(world, town), town, choice))
    return founding.my_sect(world, me), town


def texts(turn):
    return [t for t, _ in turn.lines]


def test_inviting_someone_brings_them_to_the_seat(game, monkeypatch):
    monkeypatch.setattr(founding, "follow_chance", lambda *args, **kwargs: 1.0)
    sect, town = found_sect(game)
    other = next(t.id for t in game.world.entities("town") if t.id != town)
    halls.settle_town(game.world, other)
    stranger = founding.make_person(game.world, "test:stranger", other)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, other, "located_in")
    turn = game.perform(Action("talk", stranger))
    assert Action("sect_invite", stranger) in [c.action for c in turn.all_choices]
    game.perform(Action("sect_invite", stranger))
    assert stranger in sect_mod.members(game.world, sect)
    assert game.world.targets(stranger, "located_in") == [town]


def test_teaching_makes_sect_arts(game):
    sect, town = found_sect(game)
    disciple = sect_mod.members(game.world, sect)[0]
    art = martial_arts(game.world, game.player.id)[0].technique.id
    game.perform(Action("talk", disciple))
    turn = game.perform(Action("sect_menu"))
    assert Action("sect_teach", art) in [c.action for c in turn.choices]
    game.perform(Action("sect_teach", art))
    assert art in {a.technique.id for a in known_arts(game.world, disciple)}
    assert game.world.entity(sect).data["arts"] == [art]


def test_raising_an_elder_needs_a_loyal_and_able_disciple(game):
    sect, town = found_sect(game)
    disciple = sect_mod.members(game.world, sect)[0]
    assert sect_mod.elder_block(game.world, sect, disciple) == "They are not ready to be an elder."
    game.world.update_data(disciple, realm="third-rate")
    game.perform(Action("talk", disciple))
    game.perform(Action("sect_elder", disciple))
    assert disciple in sect_mod.members(game.world, sect, roles=("elder",))


def test_duty_sends_a_disciple_away_and_back(game):
    sect, town = found_sect(game)
    disciple = sect_mod.members(game.world, sect)[0]
    game.perform(Action("talk", disciple))
    game.perform(Action("sect_duty", disciple))
    assert game.world.entity(disciple).data["on_duty"] and game.world.targets(disciple, "located_in") != [town]
    other = sect_mod.members(game.world, sect)[1]
    game.perform(Action("talk", other))
    turn = game.perform(Action("sect_menu"))
    assert Action("sect_duty", disciple) in [c.action for c in turn.choices]
    game.perform(Action("sect_duty", disciple))
    assert game.world.targets(disciple, "located_in") == [town] and not game.world.entity(disciple).data["on_duty"]


def test_expelling_leaves_a_grudge(game):
    sect, town = found_sect(game)
    disciple = sect_mod.members(game.world, sect)[0]
    game.perform(Action("talk", disciple))
    game.perform(Action("sect_expel", disciple))
    assert F.membership(game.world, disciple, sect)[1]["status"] == "expelled"
    assert any(m.feeling == "wronged" for m in game.world.memories(disciple, about=game.player.id))


def test_the_treasury_pays_for_buildings(game):
    sect, town = found_sect(game)
    disciple = sect_mod.members(game.world, sect)[0]
    game.perform(Action("talk", disciple))
    game.perform(Action("sect_treasury", 200))
    assert game.world.entity(sect).data["treasury"] == 200
    assert sect_mod.build_block(game.world, sect, "walls") == "The treasury holds 200 silver; that costs 300."
    game.perform(Action("sect_build", "training_yard"))
    data = game.world.entity(sect).data
    assert data["treasury"] == 50 and data["buildings"]["training_yard"]["done_at"] == game.world.time + 360
    assert not sect_mod.built(game.world, sect, "training_yard")
    game.perform(Action("sect_treasury", -50))
    assert game.world.entity(sect).data["treasury"] == 0


def test_other_factions_judge_the_sect_by_its_people(game):
    sect, town = found_sect(game)
    orthodox = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == "orthodox_sect")
    assert sect_mod.sect_stance(game.world, orthodox, sect) == 0.6
    seat = halls.seat_of(game.world, orthodox)
    victim = halls.staff_at(game.world, orthodox, seat, roles=("disciple",))[0]
    member = sect_mod.members(game.world, sect)[0]
    for _ in range(3):
        record_fact(game.world, member, "robbed", victim, place=seat, variant=make_variant("robbed", member, victim))
    assert sect_mod.sect_stance(game.world, orthodox, sect) == pytest.approx(0.3)


def test_an_alliance_with_a_friendly_faction(game):
    sect, town = found_sect(game)
    orthodox = next(i for i in F.ensure_roster(game.world) if game.world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(game.world, orthodox)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, seat, "located_in")
    keeper = halls.keeper_at(game.world, orthodox, seat)
    game.perform(Action("talk", keeper))
    turn = game.perform(Action("faction_menu"))
    assert Action("propose_pact", orthodox) in [c.action for c in turn.choices]
    game.perform(Action("propose_pact", orthodox))
    assert sect_mod.has_pact(game.world, sect, orthodox)
    assert game.world.facts(predicate="allied_with")[0].subject == sect


def test_disbanding_asks_twice_and_releases_everyone(game):
    sect, town = found_sect(game)
    disciple = sect_mod.members(game.world, sect)[0]
    game.perform(Action("talk", disciple))
    game.perform(Action("sect_disband", False))
    assert founding.my_sect(game.world, game.player.id) == sect
    game.perform(Action("talk", disciple))
    game.perform(Action("sect_disband", True))
    assert game.world.entity(sect).data["dissolved"] and founding.my_sect(game.world, game.player.id) is None
    assert F.membership(game.world, disciple, sect)[1]["status"] == "released"
    assert sect not in halls.halls_here(game.world, town)
