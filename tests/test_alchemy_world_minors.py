"""Phase 5c minors: small things the review left."""

import pytest

import systems.control as C
import systems.encounters as encounters
import systems.hall_theft as T
from engine.actions import Action
from engine.game import Game
from systems import factions as F
from systems import halls
from systems.bodies import load_body, save_body
from systems.creation import CreationChoice
from world.body import add_injury
from world.gen.materialize import ensure_town


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


def someone(game, tag, **data):
    base = {"occupation": "tea seller", "traits": ["curious", "honest"], "realm": "mortal", "age": 30,
            "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", f"Someone {tag}", {**base, **data}, seed_path=f"test:awminor:{tag}")
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def test_a_garden_keeps_one_guardian_until_it_is_slain(game):
    world = game.world
    sect = next(i for i in F.ensure_roster(world) if world.entity(i).data["type"] == "orthodox_sect")
    seat = halls.seat_of(world, sect)
    first = T.guardian_events(world, game.player.id, sect, seat)[0].actors[1]
    assert T.guardian_events(world, game.player.id, sect, seat)[0].actors[1] == first
    world.update_data(first, dead=True)
    assert T.guardian_events(world, game.player.id, sect, seat)[0].actors[1] != first


def test_a_message_errand_stays_put_and_is_never_where_it_starts(game):
    world, me = game.world, game.player.id
    master = someone(game, "master", occupation="bandit", realm="first-rate")
    start = game.place.id  # the master's town
    C.bind(world, me, master)
    for month in range(24):
        world.set_time(month * C.MONTH)
        task = C.service(world, me)
        if task["kind"] != "message":
            continue
        home = world.entity(start).data
        assert (task["at"][0], task["at"][1]) != (home["x"], home["y"])
        world.unrelate(me, "located_in")
        world.relate(me, ensure_town(world, *task["at"]), "located_in")
        assert C.service(world, me) == task  # going there does not move it
        assert C.service_done(world, me)
        world.unrelate(me, "located_in")
        world.relate(me, start, "located_in")


def test_a_famous_doctor_says_their_terms(game):
    world, me = game.world, game.player.id
    doctor = someone(game, "doctor", occupation="famous doctor", realm="first-rate",
                     doctor={"title": "the Needle Doctor", "whim": "task", "home": [0, 0], "block": [0, 0]})
    body = load_body(world, me)
    add_injury(body, "left arm", "cut", 5, world.time, "a test", permanent=True)
    save_body(world, me, body)
    game.perform(Action("talk", doctor))
    lines = [t for t, _ in game.perform(Action("remedies")).lines]
    assert "the Needle Doctor asks a thousand-year herb." in lines
