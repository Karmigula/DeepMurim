import systems.sect as sect_mod
from debug.invariants import check_sect
from tests.test_sect import calm, found_sect, game  # noqa: F401


def test_a_founded_sect_breaks_no_rule(game):
    found_sect(game)
    assert check_sect(game.world) == []


def test_a_member_wandering_off_is_caught(game):
    sect, town = found_sect(game)
    member = sect_mod.members(game.world, sect)[0]
    other = next(t.id for t in game.world.entities("town") if t.id != town)
    game.world.unrelate(member, "located_in")
    game.world.relate(member, other, "located_in")
    assert any("not at the seat" in p for p in check_sect(game.world))


def test_two_owners_of_one_town_are_caught(game):
    sect, town = found_sect(game)
    stranger = game.world.add_entity("person", "Land Grabber", {"realm": "mortal"})
    game.world.relate(stranger, town, "owns_land")
    assert any("owners" in p for p in check_sect(game.world))


def test_a_sect_ahead_of_time_is_caught(game):
    sect, town = found_sect(game)
    game.world.update_data(sect, last_tick=game.world.time + 999)
    assert any("ahead" in p for p in check_sect(game.world))
