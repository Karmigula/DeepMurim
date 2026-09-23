import pytest

import systems.encounters as encounters
import systems.lives as lives
import systems.world_clock as clock
from debug.invariants import check_life
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import founding, halls
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact


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


def local(game, path, **data):
    return founding.make_person(game.world, path, game.place.id, **data)


def test_a_lived_world_breaks_no_rule(game):
    halls.seat_of(game.world, F.ensure_roster(game.world)[0])
    game.world.set_time(game.world.time + 8 * lives.SEASON)
    game.perform(Action("look"))
    while clock.run_due(game.world):
        pass
    assert check_life(game.world) == []


def test_a_clock_ahead_of_time_is_caught(game):
    pid = local(game, "test:ahead", occupation="scholar")
    game.world.update_data(pid, lived_to=lives.current_season(game.world) + 3)
    game.world.set_meta("world_tick", lives.current_season(game.world) + 1)
    problems = check_life(game.world)
    assert any("lived ahead" in p for p in problems) and any("world clock" in p for p in problems)


def test_a_one_sided_or_second_spouse_is_caught(game):
    a, b, c = (local(game, f"test:s{i}", occupation="scholar", age=30) for i in range(3))
    game.world.relate(a, b, "kin_of", data={"role": "spouse"})
    assert any("spouse" in p for p in check_life(game.world))
    game.world.relate(b, a, "kin_of", data={"role": "spouse"})
    game.world.relate(a, c, "kin_of", data={"role": "spouse"})
    game.world.relate(c, a, "kin_of", data={"role": "spouse"})
    assert any("spouses" in p for p in check_life(game.world))


def test_a_dead_member_is_caught(game):
    sect = F.ensure_roster(game.world)[0]
    seat = halls.seat_of(game.world, sect)
    person = halls.staff_at(game.world, sect, seat, roles=("disciple",))[0]
    game.world.update_data(person, dead=True)
    assert any("dead but still" in p for p in check_life(game.world))


def test_two_leaders_are_caught(game):
    sect = F.ensure_roster(game.world)[0]
    seat = halls.seat_of(game.world, sect)
    elder = halls.staff_at(game.world, sect, seat, roles=("elder",))[0]
    game.world.relate(elder, sect, "member_of", 4, {**F.membership(game.world, elder, sect)[1], "role": "leader"})
    assert any("leaders" in p for p in check_life(game.world))


def test_a_child_on_staff_is_caught(game):
    sect = F.ensure_roster(game.world)[0]
    child = local(game, "test:tiny", occupation="child", age=5)
    game.world.relate(child, sect, "member_of", 0, {"role": "disciple", "status": "member", "secret": False})
    assert any("child" in p for p in check_life(game.world))


def test_a_birth_over_the_cap_is_caught(game):
    a = local(game, "test:par", occupation="scholar", age=30)
    b = local(game, "test:kid2", occupation="child", age=0)
    record_fact(game.world, a, "born", b, place=game.place.id, variant=make_variant("born", a, b), extra={"population": 999})
    assert any("born" in p for p in check_life(game.world))
