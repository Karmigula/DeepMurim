"""Findings from the phase 3c final review."""

import time

import systems.sect as sect_mod
import systems.sect_seasons as seasons
from debug.invariants import check_sect
from engine.actions import Action
from systems import factions as F
from systems import founding, halls
from systems.facts import make_variant, record_fact
from systems.techniques import known_arts, martial_arts, teach
from tests.test_sect import calm, found_sect, game  # noqa: F401  (shared fixtures)
from world.events import Event, commit


def of_type(world, kind):
    return next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == kind)


def secret_join(game, faction):
    game.world.relate(game.player.id, faction, "member_of", 0, {
        "role": "member", "hall": 0, "sponsor": None, "merit": 0, "secret": True, "joined_at": 0,
        "status": "member", "judged": [], "stipend_at": 0})


def test_the_founder_is_never_cast_out_of_their_own_sect_as_a_spy(game):
    sect, town = found_sect(game)
    cult = of_type(game.world, "demonic_cult")
    secret_join(game, cult)
    record_fact(game.world, game.player.id, "member_of", cult, place=town,
                variant=make_variant("member_of", game.player.id, cult, place=game.world.entity(town).name))
    game.perform(Action("look"))
    status = F.membership(game.world, game.player.id, sect)[1]
    assert status["status"] == "member" and status["role"] == "leader"
    assert check_sect(game.world) == []


def test_a_secret_martial_membership_also_bars_founding(game):
    from tests.test_founding import ready
    town = ready(game)
    secret_join(game, of_type(game.world, "demonic_cult"))
    assert founding.found_block(game.world, game.player.id, town) == "You must leave your martial faction first."


def test_disciples_away_on_duty_can_be_called_home_from_the_seat(game):
    sect, town = found_sect(game)
    for person in sect_mod.members(game.world, sect):
        game._commit(sect_mod.duty_events(game.world, game.player.id, person, town, True))
    turn = game.perform(Action("look"))
    assert Action("sect_recall") in [c.action for c in turn.all_choices]
    game.perform(Action("sect_recall"))
    for person in sect_mod.members(game.world, sect):
        assert game.world.targets(person, "located_in") == [town] and not game.world.entity(person).data["on_duty"]


def test_elders_teach_sect_arts_only_with_a_library(game):
    sect, town = found_sect(game)
    elder, pupil = sect_mod.members(game.world, sect)[:2]
    art = martial_arts(game.world, game.player.id)[0].technique.id
    teach(game.world, elder, art, source="sect", teacher=game.player.id)
    game.world.relate(elder, sect, "member_of", 3, {**F.membership(game.world, elder, sect)[1], "role": "elder"})
    game.world.update_data(sect, arts=[art])
    game.world.set_time(game.world.time + seasons.SEASON)
    game._commit(seasons.season_events(game.world, game.player.id, sect))
    assert art not in {a.technique.id for a in known_arts(game.world, pupil)}
    game.world.update_data(sect, buildings={"library": {"done_at": 0, "built": True}})
    game.world.set_time(game.world.time + seasons.SEASON)
    game._commit(seasons.season_events(game.world, game.player.id, sect))
    assert art in {a.technique.id for a in known_arts(game.world, pupil)}


def test_eight_seasons_for_fifteen_members_meet_the_spec(game):
    sect, town = found_sect(game)
    for i in range(12):
        founding.enrol(game.world, founding.make_person(game.world, f"test:extra:{i}", town), sect, 70)
    game.world.set_time(game.world.time + 8 * seasons.SEASON)
    start = time.perf_counter()
    for _ in range(8):
        game._commit(seasons.season_events(game.world, game.player.id, sect))
    elapsed = time.perf_counter() - start
    assert elapsed < 0.2, f"8 seasons took {elapsed * 1000:.0f} ms"


def test_the_dead_are_no_longer_members(game):
    sect, town = found_sect(game)
    member = sect_mod.members(game.world, sect)[0]
    commit(game.world, [Event("died", (member, member), town, {"cause": "duty"})])
    assert F.membership(game.world, member, sect)[1]["status"] == "dead"
    assert member not in sect_mod.members(game.world, sect)
    game.world.relate(member, sect, "member_of", 0, {**F.membership(game.world, member, sect)[1], "status": "member"})
    assert any("dead" in p for p in check_sect(game.world))


def test_a_gate_challenger_goes_home_after_the_season(game, monkeypatch):
    monkeypatch.setattr(seasons, "GATE_BASE", 1.0)
    sect, town = found_sect(game)
    game.world.set_time(game.world.time + seasons.SEASON)
    game.perform(Action("look"))
    challenger = game.challenger
    home = seasons_home = game.world.entity(sect).data["visitors"][str(challenger)]
    assert game.world.targets(challenger, "located_in") == [town] and seasons_home != town
    game.challenger = None
    monkeypatch.setattr(seasons, "GATE_BASE", 0.0)
    monkeypatch.setattr(seasons, "GATE_HOSTILE", 0.0)
    game.world.set_time(game.world.time + seasons.SEASON)
    game.perform(Action("look"))
    assert game.world.targets(challenger, "located_in") == [home]


def test_an_offstage_gate_leaves_no_stranger_living_at_the_seat(game, monkeypatch):
    monkeypatch.setattr(seasons, "GATE_BASE", 1.0)
    monkeypatch.setattr(seasons, "_hostile", lambda world, sect, people=None: [])
    sect, town = found_sect(game)
    elsewhere = next(t.id for t in game.world.entities("town") if t.id != town)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, elsewhere, "located_in")
    before = {p for p in game.world.sources(town, "located_in")}
    game.world.set_time(game.world.time + seasons.SEASON)
    game._commit(seasons.season_events(game.world, game.player.id, sect))
    arrived = {p for p in game.world.sources(town, "located_in")} - before
    assert all(p in sect_mod.members(game.world, sect) for p in arrived)
    assert halls  # the seat keeps only the sect's own people
