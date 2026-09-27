import random

import pytest

import systems.toxins as X
from debug.invariants import check_toxins
from engine.game import Game
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from world.body import WATCHES_PER_DAY
from world.events import commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["curious", "honest"], "realm": "mortal",
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:tox:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def later(world, watches):
    world.set_time(world.time + watches)


def set_realm(world, person, realm):
    body = load_body(world, person)
    body.realm = realm
    body.energy_years = {0: 0.0, 1: 1.0, 2: 5.0, 3: 20.0}[realm]
    save_body(world, person, body)


def test_residue_dulls_pills_and_fades_with_time(game):
    world, me = game.world, game.player.id
    body = load_body(world, me)
    assert X.dulling(body) == 1.0
    X.leave_residue(body, 3, 0.4, random.Random(1))
    assert body.residue == pytest.approx(18.0) and X.dulling(body) == pytest.approx(1 - 18 / 150)
    save_body(world, me, body)
    later(world, 7 * WATCHES_PER_DAY)
    assert load_body(world, me).residue < 18.0


def test_a_body_full_of_residue_risks_deviation_and_its_meridians(game):
    world, me = game.world, game.player.id
    body = load_body(world, me)
    body.residue = 95.0
    harms = X.leave_residue(body, 1, 0.9, random.Random(4))
    assert set(harms) <= {"deviation", "meridian"}
    clean = load_body(world, me)
    assert X.leave_residue(clean, 1, 0.9, random.Random(4)) == []  # below the thresholds: no risk


def test_a_poison_spreads_does_harm_each_day_and_ebbs(game):
    world, me = game.world, game.player.id
    X.poison(world, me, 2, 2 * WATCHES_PER_DAY, "test")
    later(world, WATCHES_PER_DAY)
    body = load_body(world, me)
    [p] = body.poisons
    assert p["strength"] == WATCHES_PER_DAY and any(i.cause == "poison" for i in body.injuries)
    later(world, 2 * WATCHES_PER_DAY)
    assert load_body(world, me).poisons == []  # spent


def test_a_strong_poison_that_outlasts_the_body_kills(game):
    world = game.world
    victim = someone(game, "victim")
    X.poison(world, victim, 5, 20, "test")
    assert world.get_meta("poisoned") == [victim] and check_toxins(world) == []
    assert X.death_events(world, victim) == []
    later(world, 3 * WATCHES_PER_DAY + 1)  # a mortal lasts realm + 2 days
    [died] = X.death_events(world, victim)
    assert died.kind == "died" and died.data["cause"] == "poisoned"


def test_sealing_the_acupoints_halts_the_spread(game):
    world, me = game.world, game.player.id
    X.poison(world, me, 2, 10, "test")
    assert X.seal_block(load_body(world, me), world.time) is not None  # a mortal cannot seal
    set_realm(world, me, 1)
    assert X.seal_block(load_body(world, me), world.time) is None
    commit(world, X.seal_events(world, me, game.place.id))
    later(world, X.SEAL_WATCHES)
    assert load_body(world, me).poisons[0]["strength"] == 10  # nothing spread while sealed
    assert X.seal_block(load_body(world, me), world.time) is None  # the seal has lapsed


def test_a_master_forces_the_poison_out(game):
    world, me = game.world, game.player.id
    set_realm(world, me, 2)
    X.poison(world, me, 1, 10, "test")
    assert X.force_block(load_body(world, me)) == "Only a first-rate master can force a poison out."
    set_realm(world, me, 3)
    body = load_body(world, me)
    body.qi = 50.0
    save_body(world, me, body)
    assert X.force_block(load_body(world, me)) is None
    [forced] = X.force_events(world, me, game.place.id)
    assert forced.data["cleared"]
    commit(world, [forced])
    assert load_body(world, me).poisons == []


def test_an_antidote_cures_poisons_of_its_grade_or_less(game):
    world = game.world
    victim = someone(game, "cured")
    X.poison(world, victim, 2, 10, "a")
    X.poison(world, victim, 4, 10, "b")
    assert X.cure(world, victim, 3) == 1
    assert [p["grade"] for p in load_body(world, victim).poisons] == [4]
    assert X.cure(world, victim, 5) == 1 and world.get_meta("poisoned") == []


def test_a_resistant_body_lets_a_weak_poison_pass(game):
    world, me = game.world, game.player.id
    body = load_body(world, me)
    body.resist = 2
    save_body(world, me, body)
    assert X.poison(world, me, 2, 10, "test") == "resisted" and load_body(world, me).poisons == []


def test_the_dead_leave_the_poisoned_index(game):
    world = game.world
    victim = someone(game, "gone")
    X.poison(world, victim, 5, 20, "test")
    later(world, 4 * WATCHES_PER_DAY)
    commit(world, X.season_hook(world, 1))
    assert world.entity(victim).data.get("dead")
    X.season_hook(world, 2)
    assert world.get_meta("poisoned") == []
