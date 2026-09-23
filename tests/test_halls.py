import sqlite3

import pytest

from engine.actions import Action
from engine.game import Game
from render.art import compose_scene, load_art
from systems import factions as F
from systems import halls
from systems.creation import CreationChoice
from world.gen.materialize import ensure_town, people_at


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def first_sect(world):
    return next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")


def move_to(game, town):
    halls.settle_town(game.world, town)
    game.world.unrelate(game.player.id, "located_in")
    game.world.relate(game.player.id, town, "located_in")


def test_a_seat_has_a_leader_two_elders_a_keeper_and_disciples(game):
    sect = first_sect(game.world)
    seat = halls.seat_of(game.world, sect)
    assert game.world.entity(sect).data["seat"] == seat
    roles = sorted(F.membership(game.world, p, sect)[1]["role"] for p in halls.staff_at(game.world, sect, seat))
    assert roles == ["disciple"] * 4 + ["elder", "elder", "keeper", "leader"]
    assert sorted(halls.elders(game.world, sect)) == [0, 1]
    assert sect in halls.halls_here(game.world, seat)
    leader = halls.staff_at(game.world, sect, seat, roles=("leader",))[0]
    assert F.membership(game.world, leader, sect)[0] == 4
    halls.settle_town(game.world, seat)
    assert len(halls.staff_at(game.world, sect, seat)) == 8


def test_constables_beggars_and_merchants_join_their_factions_naturally(game):
    for x in range(-2, 3):
        town = ensure_town(game.world, x, 1, 0)
        halls.settle_town(game.world, town)
        for person in people_at(game.world, town):
            kind = F.NATURAL.get(person.data.get("occupation"))
            if kind:
                assert any(game.world.entity(fid).data["type"] == kind for fid, _, _ in F.memberships(game.world, person.id))


def test_the_start_town_is_settled_from_the_first_turn(game):
    assert game.world.entity(game.place.id).data["factions_ready"]


def test_a_seat_town_says_so_tags_its_people_and_shows_its_gate(game):
    sect = first_sect(game.world)
    seat = halls.seat_of(game.world, sect)
    move_to(game, seat)
    turn = game.perform(Action("look"))
    name = game.world.entity(sect).name
    text = [t for t, _ in turn.lines]
    assert f"The {name} keeps its seat here." in text
    assert any(f"({name})" in t for t in text if t.startswith("Here:"))
    assert turn.art["hall"] == "gate"


def test_the_faction_menu_needs_someone_to_talk_to(game):
    sect = first_sect(game.world)
    seat = halls.seat_of(game.world, sect)
    move_to(game, seat)
    keeper = halls.keeper_at(game.world, sect, seat)
    assert sect in halls.recruits_for(game.world, keeper)
    turn = game.perform(Action("faction_menu"))  # not talking to anyone
    assert turn.lines[-1] == ("There is no one to discuss that with.", "system")


def test_the_conversation_menu_stays_within_nine(game):
    sect = first_sect(game.world)
    move_to(game, halls.seat_of(game.world, sect))
    for npc in people_at(game.world, game.place.id, exclude=game.player.id):
        turn = game.perform(Action("talk", npc.id))
        assert len(turn.choices) <= 9 and turn.choices[-1].action == Action("farewell")
        game.perform(Action("farewell"))


def test_the_hall_art_exists_and_fits():
    for name in ("gate", "hall"):
        art = load_art(name)
        assert art and max(len(r) for r in art) <= 20 and len(art) <= 8
    assert compose_scene("mountains", "town", 1, 40, 18, hall="gate")


def test_an_old_save_gets_factions_on_load(tmp_path):
    path = tmp_path / "old.world"
    g = Game.new(path, "Old", world_seed=5)
    g.close()
    conn = sqlite3.connect(path)
    conn.execute("delete from meta where key = 'roster'")
    conn.execute("delete from relations where kind in ('stance', 'member_of')")
    conn.execute("delete from entities where kind = 'faction'")
    conn.execute("update entities set data = json_remove(data, '$.factions_ready', '$.halls', '$.seats') where kind = 'town'")
    conn.execute("update entities set data = json_remove(data, '$.minors_ready', '$.minors') where kind = 'region'")
    conn.commit()
    conn.close()
    g = Game.load(path)
    g.start()
    assert len(g.world.get_meta("roster")) == 10
    assert g.world.entity(g.place.id).data["factions_ready"]
    g.close()
