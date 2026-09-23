import pytest

from engine.game import Game
from systems.bodies import ensure_body, load_body
from systems.creation import ORIGINS, CreationChoice, build, point_buy_problem
from systems.techniques import heart_method, known_arts, martial_arts
from world.body import REGULAR
from world.db import World

POINTS = {"strength": 12, "agility": 12, "endurance": 8, "comprehension": 10}  # 10 points spent


def test_each_origin_builds_its_kit():
    for key, origin in ORIGINS.items():
        made = build(7, CreationChoice("origin", key))
        assert made.origin.key == key and made.silver == origin.silver
        heart, art = made.arts
        assert heart[1]["category"] == "heart_method" and heart[1]["grade"] == origin.heart_grade
        assert art[1]["form"] in origin.art_forms
    scion = build(7, CreationChoice("origin", "scion"))
    assert scion.arts[0][2] == 0.8  # the family method's hidden flaw
    assert sum(scion.body.meridians[m].state == "scarred" for m in REGULAR) == 1
    assert build(7, CreationChoice("origin", "temple")).arts[0][1]["element"] == "yang"


def test_random_mode_is_seeded():
    a, b = build(11, CreationChoice()), build(11, CreationChoice())
    assert a.origin.key == b.origin.key and a.arts[1][0] == b.arts[1][0]
    assert {build(s, CreationChoice()).origin.key for s in range(40)} == set(ORIGINS)


def test_point_buy():
    assert point_buy_problem(POINTS, 1) is None
    made = build(3, CreationChoice("point_buy", physique=tuple(POINTS.items()), flow_points=1, form="saber"))
    assert made.body.physique == POINTS and made.arts[1][1]["form"] == "saber" and made.silver == 50
    assert "points spent" in point_buy_problem({**POINTS, "endurance": 16}, 0)
    assert point_buy_problem({**POINTS, "agility": 17}, 0)
    with pytest.raises(ValueError):
        build(3, CreationChoice("point_buy", physique=tuple(POINTS.items()), form="banjo"))


def test_choice_roundtrips_through_dict():
    choice = CreationChoice("point_buy", physique=tuple(POINTS.items()), flow_points=1, form="saber")
    assert CreationChoice.from_dict(choice.to_dict()) == choice
    assert CreationChoice.from_dict(CreationChoice().to_dict()) == CreationChoice()


def test_new_game_applies_creation(tmp_path):
    game = Game.new(tmp_path / "g.world", "Hero", world_seed=5, creation=CreationChoice("origin", "merchant"))
    player = game.player
    assert player.data["silver"] == 200 and player.data["origin"] == "merchant"
    assert load_body(game.world, player.id).realm == 0
    assert heart_method(game.world, player.id) is not None and len(martial_arts(game.world, player.id)) == 1
    began = game.world.chronicle_about(player.id, limit=5)[-1]
    assert began.kind == "began" and began.data["origin"] == "Merchant's runaway" and len(began.data["arts"]) == 2
    game.close()


def test_old_saves_get_a_body_on_load(tmp_path):
    path = tmp_path / "old.world"
    game = Game.new(path, "Hero", world_seed=5)
    pid = game.player.id
    game.world._conn.execute(
        "update entities set data = json_remove(data, '$.body', '$.silver', '$.origin') where id = ?", (pid,)
    )
    game.world._conn.execute("delete from relations where a = ? and kind = 'knows'", (pid,))
    game.close()
    game = Game.load(path)
    assert "body" in game.player.data and game.player.data["origin"] == "wanderer"
    assert len(known_arts(game.world, pid)) == 2
    assert game.world.chronicle_about(pid, limit=1)[0].kind == "body_awakened"
    game.close()


def test_npc_bodies_follow_their_realm(tmp_path):
    world = World.create(tmp_path / "w.world", 9)
    npc = world.add_entity("person", "Old Master", {"realm": "second-rate"}, seed_path="npc:test")
    body = ensure_body(world, npc)
    assert body.realm == 2 and 5 <= body.energy_years < 20
    assert "sensed_qi" in body.flags and body.meridians["Governing"].state == "open"
    assert "body" in world.entity(npc).data
    assert ensure_body(world, npc).energy_years == body.energy_years
    world.close()
