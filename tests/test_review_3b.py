"""Findings from the phase 3b final review."""

import time

import pytest

import systems.duties as duties
import systems.encounters as encounters
import systems.law as law
import systems.leaving as leaving
import systems.telling as telling
from debug.invariants import check_people, check_world
from engine.actions import Action
from engine.game import Game
from engine.standing_page import standing_lines
from systems import factions as F
from systems import halls, membership
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from systems.politics import breaches
from systems.standing import believed_factions
from world.events import Event, commit
from world.gen.materialize import ensure_region, ensure_town, people_at
from world.gen.region import region_spec


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


def of_type(world, kind):
    return next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == kind)


def go(game, town):
    halls.settle_town(game.world, town)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, town, "located_in")


def join(game, faction, rank=0, status="member"):
    game.world.relate(game.player.id, faction, "member_of", rank, {
        "role": "member", "hall": 0, "sponsor": halls.elders(game.world, faction).get(0)
        if game.world.entity(faction).data["type"] in F.STAFFED else None,
        "merit": 0, "secret": False, "joined_at": 0, "status": status, "judged": [], "stipend_at": 0})


def town_with_hall(game, faction):
    for x in range(-3, 4):
        for y in range(-3, 4):
            for i in range(region_spec(game.world.world_seed, x, y).town_count):
                town = ensure_town(game.world, x, y, i)
                halls.settle_town(game.world, town)
                if faction in halls.halls_here(game.world, town) and halls.keeper_at(game.world, faction, town):
                    return town
    raise AssertionError("no hall")


def innocent(game, town, name="Hu Mei"):
    pid = game.world.add_entity("person", name, {"realm": "mortal", "occupation": "innkeeper"})
    game.world.relate(pid, town, "located_in")
    return pid


def deed(game, predicate, target, town, actor=None):
    actor = actor or game.player.id
    return record_fact(game.world, actor, predicate, target, place=town,
                       variant=make_variant(predicate, actor, target, place=game.world.entity(town).name))


def test_a_summons_and_an_arrest_never_lock_the_game_together(game, monkeypatch):
    monkeypatch.setattr(law, "ARREST_CHANCE", 1.0)
    bureau = of_type(game.world, "imperial")
    town = town_with_hall(game, bureau)
    sect = of_type(game.world, "orthodox_sect")
    go(game, town)
    game.world.update_data(town, halls=[*halls.halls_here(game.world, town), sect])
    game.world.update_data(sect, branches=[*game.world.entity(sect).data["branches"], town])
    join(game, sect)
    deed(game, "killed", innocent(game, town), town)
    game.perform(Action("look"))
    data = game.player.data
    assert bool(data.get("summons")) != bool(data.get("arrest"))


def test_a_dead_recruiter_ends_the_ears_trial(game):
    beggars = of_type(game.world, "beggars")
    town = town_with_hall(game, beggars)
    go(game, town)
    keeper = halls.keeper_at(game.world, beggars, town)
    game.perform(Action("talk", keeper))
    game.perform(Action("join", beggars))
    assert game.player.data["trial"]["deadline"] is not None
    commit(game.world, [Event("died", (game.player.id, keeper), town, {"cause": "killed"})])
    game.perform(Action("look"))
    assert game.player.data.get("trial") is None


def test_guarding_longer_than_asked_still_counts(game, monkeypatch):
    monkeypatch.setattr(duties, "RAID_CHANCE", 0.0)
    sect = of_type(game.world, "orthodox_sect")
    seat = halls.seat_of(game.world, sect)
    go(game, seat)
    join(game, sect)
    game._commit(duties.issue_events(game.world, game.player.id, sect, halls.keeper_at(game.world, sect, seat), seat, kind="guard"))
    game.perform(Action("meditate", 30))
    assert game.world.entity(game.world.entity(game.player.id).data.get("duty") or 0) is None \
        or duties.open_duty(game.world, game.player.id) is None
    assert any(e.kind == "duty_done" for e in game.world.chronicle_about(game.player.id, limit=10))


def test_beating_a_clan_elder_in_a_trial_is_no_crime(game):
    clan = of_type(game.world, "martial_clan")
    seat = halls.seat_of(game.world, clan)
    go(game, seat)
    join(game, clan)
    elder = halls.elders(game.world, clan)[1]
    deed(game, "defeated", elder, seat)
    assert breaches(game.world, game.player.id, clan) == []


def test_leaving_closes_the_open_duty_and_a_deserter_is_not_released(game):
    guild = of_type(game.world, "merchant_guild")
    town = town_with_hall(game, guild)
    go(game, town)
    join(game, guild)
    keeper = halls.keeper_at(game.world, guild, town)
    game.perform(Action("talk", keeper))
    game.perform(Action("release_duty", guild))
    duty = game.player.data["duty"]
    game.world.update_data(duty, kind="deliver", town=town)
    game.perform(Action("desert", guild))
    assert duties.open_duty(game.world, game.player.id) is None
    game.perform(Action("look"))
    assert F.membership(game.world, game.player.id, guild)[1]["status"] == "deserter"


def test_deadlines_leave_time_to_walk_the_roads(game):
    sect = of_type(game.world, "orthodox_sect")
    seat = halls.seat_of(game.world, sect)
    go(game, seat)
    join(game, sect)
    keeper = halls.keeper_at(game.world, sect, seat)
    here = game.world.entity(seat).data
    for n in range(12):
        game.world.update_data(game.player.id, duties_taken=n, duty=None)
        for kind in ("deliver", "gather"):
            [event] = duties.issue_events(game.world, game.player.id, sect, keeper, seat, kind=kind)
            d = event.data
            where = d["town"] if kind == "deliver" else game.world.targets(d["target"], "located_in")[0]
            there = game.world.entity(where).data
            road_days = 3 * (abs(there["x"] - here["x"]) + abs(there["y"] - here["y"])) + 1
            assert d["deadline"] - game.world.time >= road_days * 4, (kind, road_days)


def test_a_bandit_fort_offers_tribute_before_any_fight(game):
    fort = None
    for x in range(-4, 5):
        for y in range(-4, 5):
            for fid in F.minor_factions(game.world, game.world.entity(ensure_region(game.world, x, y))):
                if game.world.entity(fid).data["type"] == "bandit_fort":
                    fort = fid
    assert fort is not None
    seat = game.world.entity(fort).data["seat"]
    go(game, seat)
    game.perform(Action("talk", halls.keeper_at(game.world, fort, seat)))
    game.perform(Action("join", fort))
    assert game.combat is None
    options = {c.action.verb for c in game.perform(Action("faction_menu")).choices}
    assert {"tribute", "chief_duel"} <= options


def test_hunters_are_the_sect_near_home_not_every_merchant(game):
    guild = of_type(game.world, "merchant_guild")
    town = town_with_hall(game, guild)
    join(game, guild, status="deserter")
    natural = [p.id for p in people_at(game.world, town) if p.data.get("occupation") == "merchant"]
    assert natural and not set(natural) & leaving.town_hunters(game.world, game.player.id)


def test_a_release_supersedes_an_old_membership(game):
    sect, cult = of_type(game.world, "orthodox_sect"), of_type(game.world, "demonic_cult")
    seat = halls.seat_of(game.world, cult)
    deed(game, "member_of", sect, seat)
    assert sect in believed_factions(game.world, cult, game.player.id)
    game.world.set_time(game.world.time + 1)
    deed(game, "released", sect, seat)
    assert sect not in believed_factions(game.world, cult, game.player.id)


def test_a_fallback_raider_can_be_spoken_to(game, monkeypatch):
    monkeypatch.setattr(duties, "_hostile_member", lambda *args, **kwargs: None)
    sect = of_type(game.world, "orthodox_sect")
    seat = halls.seat_of(game.world, sect)
    go(game, seat)
    join(game, sect)
    game._commit(duties.issue_events(game.world, game.player.id, sect, halls.keeper_at(game.world, sect, seat), seat, kind="guard"))
    raider = duties.raider(game.world, duties.open_duty(game.world, game.player.id), seat)
    assert game.perform(Action("talk", raider)).art["type"] == "portrait"


def test_f6_names_no_rival_you_never_met(game):
    sect = of_type(game.world, "orthodox_sect")
    seat = halls.seat_of(game.world, sect)
    go(game, seat)
    game._commit(membership.joined_events(game.world, game.player.id, halls.keeper_at(game.world, sect, seat), sect, seat, False))
    rival = game.world.entity(game.player.data["rivals"][str(sect)]).name
    assert not any(rival in text for text, _ in standing_lines(game.world, game.player.id, seat))


def test_a_member_in_a_gossip_heavy_world_stays_quick(game):
    for x in range(-2, 3):
        for y in range(-2, 3):
            for i in range(region_spec(game.world.world_seed, x, y).town_count):
                halls.settle_town(game.world, ensure_town(game.world, x, y, i))
    towns = [t.id for t in game.world.entities("town")]
    with game.world.transaction():
        for n in range(1000):
            story = {"predicate": "defeated", "actor": 999, "target": 998, "n": n}
            fid = game.world.add_fact(999, "defeated", 998, place=towns[0], data={"variant": story})
            for town in towns:
                game.world.upsert_belief(town, fid, story, None, 0.5, 2, "distance")
    for kind in ("imperial", "beggars", "orthodox_sect"):
        join(game, of_type(game.world, kind))
    check_world(game.world)
    start = time.perf_counter()
    turn = game.perform(Action("look"))
    check_world(game.world)
    check_people(game, turn)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.15, f"a member's turn took {elapsed * 1000:.0f} ms"
