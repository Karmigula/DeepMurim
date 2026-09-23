"""The deferred minors from the phase 3c final review."""

import systems.sect as sect_mod
import systems.sect_seasons as seasons
from engine.actions import Action
from engine.standing_page import faction_facts
from systems import factions as F
from systems import founding
from tests.test_sect import calm, found_sect, game  # noqa: F401  (shared fixtures)
from world.seed import rng_for


def of_type(world, kind):
    return next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == kind)


def away(game, town):
    elsewhere = next(t.id for t in game.world.entities("town") if t.id != town)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, elsewhere, "located_in")


def test_a_dead_waiting_challenger_is_forgotten(game):
    sect, town = found_sect(game)
    corpse = founding.make_person(game.world, "test:corpse", town)
    game.world.update_data(corpse, dead=True)
    game.world.update_data(game.player.id, gate_challenger=corpse)
    game.perform(Action("look"))
    assert game.player.data.get("gate_challenger") is None and game.challenger is None


def test_only_one_challenger_waits_at_the_gate(game, monkeypatch):
    monkeypatch.setattr(seasons, "GATE_BASE", 1.0)
    sect, town = found_sect(game)
    game.world.set_time(game.world.time + 3 * seasons.SEASON)
    game.perform(Action("look"))
    deferred = [e.data["gate"] for e in game.world.chronicle_about(game.player.id, limit=40)
                if e.kind == "sect_season" and (e.data["gate"] or {}).get("deferred")]
    assert len(deferred) == 1 and game.challenger == deferred[0]["challenger"]
    assert game.world.targets(game.challenger, "located_in") == [town]


def test_the_expelled_leave_the_seat_for_another_town(game):
    sect, town = found_sect(game)
    disciple = sect_mod.members(game.world, sect)[0]
    game.perform(Action("talk", disciple))
    game.perform(Action("sect_expel", disciple))
    [where] = game.world.targets(disciple, "located_in")
    assert where != town and game.world.entity(where).kind == "town"


def test_a_deserter_on_duty_comes_off_the_road(game, monkeypatch):
    monkeypatch.setattr(seasons, "DESERT_CHANCE", 1.0)
    sect, town = found_sect(game)
    member = sect_mod.members(game.world, sect)[0]
    game._commit(sect_mod.duty_events(game.world, game.player.id, member, town, True))
    game.world.update_data(member, loyalty=0)
    away(game, town)
    game.world.set_time(game.world.time + seasons.SEASON)
    game._commit(seasons.season_events(game.world, game.player.id, sect))
    assert F.membership(game.world, member, sect)[1]["status"] == "deserter"
    [where] = game.world.targets(member, "located_in")
    assert not game.world.entity(member).data["on_duty"] and game.world.entity(where).kind == "town" and where != town


def test_disbanding_brings_everyone_off_the_road(game):
    sect, town = found_sect(game)
    member = sect_mod.members(game.world, sect)[0]
    game._commit(sect_mod.duty_events(game.world, game.player.id, member, town, True))
    game._commit(sect_mod.disband_events(game.world, game.player.id, town))
    [where] = game.world.targets(member, "located_in")
    assert not game.world.entity(member).data["on_duty"] and game.world.entity(where).kind == "town"


def test_the_brief_names_your_sect_before_other_ties(game):
    beggars = of_type(game.world, "beggars")
    game.world.relate(game.player.id, beggars, "member_of", 0, {"role": "member", "status": "member", "secret": False})
    sect, town = found_sect(game)
    assert faction_facts(game.world, game.player.id, None)[0].startswith("You lead the Test Pine Sect")


def test_a_guest_hall_makes_gate_news_carry_further(game, monkeypatch):
    monkeypatch.setattr(seasons, "GATE_BASE", 1.0)
    sect, town = found_sect(game)
    away(game, town)
    game.world.set_time(game.world.time + seasons.SEASON)
    game._commit(seasons.season_events(game.world, game.player.id, sect))
    game.world.update_data(sect, buildings={"guest_hall": {"done_at": 0, "built": True}})
    game.world.set_time(game.world.time + seasons.SEASON)
    game._commit(seasons.season_events(game.world, game.player.id, sect))
    weights = [f.weight for f in game.world.facts(subject=sect) if f.predicate in ("defended_gate", "gate_breached")]
    assert weights == [1.0, 1.5]


def test_an_invitee_hears_the_terms(game, monkeypatch):
    monkeypatch.setattr(founding, "follow_chance", lambda *args, **kwargs: 1.0)
    sect, town = found_sect(game)
    stranger = founding.make_person(game.world, "test:stranger", town)
    game.perform(Action("talk", stranger))
    turn = game.perform(Action("sect_invite", stranger))
    assert any("a sparring match" in text for text, _ in turn.lines)


def test_talent_follows_the_seed_path_not_the_id(game):
    sect, town = found_sect(game)
    game.world.add_entity("person", "Filler", {"realm": "mortal"})  # shifts every later id
    person = founding.make_person(game.world, "test:talented", town)
    founding.enrol(game.world, person, sect, 50)
    expected = round(rng_for(game.world.world_seed, "talent:test:talented").uniform(0.5, 1.5), 2)
    assert game.world.entity(person).data["talent"] == expected
