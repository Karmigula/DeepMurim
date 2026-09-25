import time
from collections import Counter

import pytest

import systems.encounters as encounters
import systems.lives as lives
import systems.wars as wars
import systems.world_clock as clock
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from world.events import Event, commit
from world.gen.materialize import ensure_region, ensure_town
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


def seasons_pass(game, n):
    clock.world_tick(game.world)  # the clock starts at its first reading; start it before time moves
    game.world.set_time(game.world.time + n * lives.SEASON)


def a_minor(game, settled=True):
    for x in range(-4, 5):
        for y in range(-4, 5):
            region = game.world.entity(ensure_region(game.world, x, y))
            for fid in F.minor_factions(game.world, region):
                seat = game.world.entity(fid).data["seat"]
                if settled:
                    halls.settle_town(game.world, seat)
                    return fid
                if not game.world.entity(seat).data.get("factions_ready"):
                    return fid
    raise AssertionError("no minor faction")


def roles_at(world, faction, town):
    return Counter(F.membership(world, p, faction)[1]["role"] for p in halls.staff_at(world, faction, town))


def test_the_faction_clock_runs_at_most_eight_seasons_at_a_time(game):
    start = clock.world_tick(game.world)
    assert start == lives.current_season(game.world)
    seasons_pass(game, 20)
    assert [clock.run_due(game.world) for _ in range(4)] == [8, 8, 4, 0]
    assert clock.world_tick(game.world) == lives.current_season(game.world) == start + 20


def test_power_drifts_toward_its_target(game):
    sect = of_type(game.world, "orthodox_sect")
    halls.seat_of(game.world, sect)
    game.world.update_data(sect, power=100)
    target = clock.power_target(game.world, sect)
    seasons_pass(game, 1)
    clock.run_due(game.world)
    assert abs(game.world.entity(sect).data["power"] - target) < 100 - target


def test_hostile_factions_clash_and_their_stance_hardens(game, monkeypatch):
    monkeypatch.setattr(wars, "CLASH_CHANCE", 1.0)
    monkeypatch.setattr(wars, "WAR_CHANCE", 1.0)
    monkeypatch.setattr(wars, "KILL_CHANCE", 0.0)
    sect, cult = of_type(game.world, "orthodox_sect"), of_type(game.world, "demonic_cult")
    before = F.stance(game.world, sect, cult)
    seasons_pass(game, 1)
    clock.run_due(game.world)
    assert F.stance(game.world, sect, cult) == pytest.approx(before - wars.STANCE_HIT)
    pairs = {frozenset((f.subject, f.object)) for f in game.world.facts(predicate="clashed_with")}
    assert frozenset((sect, cult)) in pairs


def test_without_clashes_stances_mend_toward_their_base(game, monkeypatch):
    monkeypatch.setattr(wars, "CLASH_CHANCE", 0.0)
    monkeypatch.setattr(wars, "WAR_CHANCE", 0.0)
    sect, cult = of_type(game.world, "orthodox_sect"), of_type(game.world, "demonic_cult")
    game.world.relate(sect, cult, "stance", -0.9)
    game.world.relate(cult, sect, "stance", -0.9)
    seasons_pass(game, 1)
    clock.run_due(game.world)
    assert F.stance(game.world, sect, cult) == pytest.approx(-0.88)
    assert F.stance(game.world, cult, sect) == pytest.approx(-0.88)


def test_a_clash_can_kill_and_take_a_hall(game, monkeypatch):
    monkeypatch.setattr(wars, "CLASH_CHANCE", 1.0)
    monkeypatch.setattr(wars, "WAR_CHANCE", 1.0)
    monkeypatch.setattr(wars, "KILL_CHANCE", 1.0)
    monkeypatch.setattr(wars, "HALL_LOSS", 1.0)
    sect, cult = of_type(game.world, "orthodox_sect"), of_type(game.world, "demonic_cult")
    town = halls.seat_of(game.world, sect)
    halls.seat_of(game.world, cult)
    game.world.update_data(town, halls=[*halls.halls_here(game.world, town), cult])
    game.world.update_data(cult, branches=[*game.world.entity(cult).data["branches"], town], power=0)
    game.world.update_data(sect, power=100)
    halls._hire(game.world, game.world.entity(cult), town, halls.BRANCH_STAFF)
    branch_staff = halls.staff_at(game.world, cult, town)
    seasons_pass(game, 1)
    clock.run_due(game.world)
    assert cult not in halls.halls_here(game.world, town)
    assert game.world.facts(predicate="lost_hall", subject=cult)
    dead = [p for p in branch_staff if game.world.entity(p).data.get("dead")]
    assert dead and all(F.membership(game.world, p, cult)[1]["status"] == "dead" for p in dead)
    survivors = [p for p in branch_staff if p not in dead]  # let go where they stood (4a minors)
    assert all(game.world.targets(p, "located_in") == [town] for p in survivors)
    assert all(F.membership(game.world, p, cult)[1]["status"] == "released" for p in survivors)


def test_a_dead_leader_is_succeeded_and_the_hall_restaffed(game, monkeypatch):
    import systems.succession_crisis as SC
    monkeypatch.setattr(SC, "doubt", lambda world, faction: None)  # 4a's handover; 4g's crises are tested apart
    sect = of_type(game.world, "orthodox_sect")
    seat = halls.seat_of(game.world, sect)
    [leader] = halls.staff_at(game.world, sect, seat, roles=("leader",))
    elders = halls.staff_at(game.world, sect, seat, roles=("elder",))
    commit(game.world, [Event("died", (leader, leader), seat, {"cause": "age", "world": True})])
    assert F.membership(game.world, leader, sect)[1]["status"] == "dead"
    seasons_pass(game, 1)
    clock.run_due(game.world)
    [heir] = halls.staff_at(game.world, sect, seat, roles=("leader",))
    best = min(elders, key=lambda p: (-F.membership(game.world, p, sect)[0], p))
    assert heir in elders and heir == min(
        elders, key=lambda p: (-lives.realm_index(game.world.entity(p).data["realm"]), p)) or heir == best
    assert F.membership(game.world, heir, sect)[0] == 4
    assert game.world.facts(predicate="promoted", subject=heir)
    assert roles_at(game.world, sect, seat) == Counter(r for r, _, _ in halls.SEAT_STAFF)


def test_a_weak_minor_faction_is_destroyed(game, monkeypatch):
    monkeypatch.setattr(clock, "DESTROY_BELOW", 101)
    minor = a_minor(game)
    seat = game.world.entity(minor).data["seat"]
    staff = halls.staff_at(game.world, minor, seat)
    seasons_pass(game, 1)
    clock.run_due(game.world)
    assert game.world.entity(minor).data["dissolved"]
    assert minor not in halls.halls_here(game.world, seat)
    assert all(F.membership(game.world, p, minor)[1]["status"] in ("released", "dead") for p in staff)
    assert game.world.facts(predicate="faction_destroyed", subject=minor)


def test_great_factions_are_never_destroyed(game, monkeypatch):
    monkeypatch.setattr(clock, "DESTROY_BELOW", 101)
    seasons_pass(game, 1)
    clock.run_due(game.world)
    assert not any(game.world.entity(f).data.get("dissolved") for f in F.ensure_roster(game.world))


def test_new_minor_factions_are_founded(game, monkeypatch):
    monkeypatch.setattr(clock, "FOUND_CHANCE", 1.0)
    for i in range(region_spec(game.world.world_seed, 0, 0).town_count):
        halls.settle_town(game.world, ensure_town(game.world, 0, 0, i))
    seasons_pass(game, 1)
    clock.run_due(game.world)
    founded = game.world.facts(predicate="faction_founded")
    assert founded
    fid = founded[0].subject
    seat = game.world.entity(fid).data["seat"]
    assert fid in halls.halls_here(game.world, seat)
    assert halls.staff_at(game.world, fid, seat, roles=("leader",))


def test_settling_skips_destroyed_factions(game):
    minor = a_minor(game, settled=False)
    seat = game.world.entity(minor).data["seat"]
    game.world.update_data(minor, dissolved=True)
    halls.settle_town(game.world, seat)
    assert minor not in halls.halls_here(game.world, seat)


def test_the_same_seeds_give_the_same_world(game, tmp_path):
    twin = Game.new(tmp_path / "twin.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    twin.start()
    results = []
    for g in (game, twin):
        halls.seat_of(g.world, of_type(g.world, "orthodox_sect"))
        seasons_pass(g, 8)
        clock.run_due(g.world)
        results.append(sorted((f, g.world.entity(f).data["power"]) for f in wars.clock_factions(g.world)))
    twin.close()
    assert results[0] == results[1]


def test_one_faction_season_is_quick(game):
    for x in range(-1, 2):
        for y in range(-1, 2):
            for i in range(region_spec(game.world.world_seed, x, y).town_count):
                halls.settle_town(game.world, ensure_town(game.world, x, y, i))
    seasons_pass(game, 1)
    start = time.perf_counter()
    clock.run_due(game.world)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.03, f"a faction season took {elapsed * 1000:.0f} ms"
