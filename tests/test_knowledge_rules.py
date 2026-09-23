import pytest

import systems.encounters as encounters
import systems.masks as masks
import systems.rumours as rumours
from debug.invariants import check_knowledge, check_people
from engine.actions import Turn
from engine.game import Action, Game
from engine.sheet import sheet_lines
from systems.attitude import attitude
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from systems.reputation import reputation
from world.gen.materialize import ensure_town, people_at


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def test_the_name_rule_catches_a_stranger_named_on_screen(game):
    far = ensure_town(game.world, 4, 4, 0)
    zhao = game.world.add_entity("person", "Zhao Yun", {"realm": "mortal"})
    game.world.relate(zhao, far, "located_in")
    turn = Turn([("Zhao Yun waves from afar.", "npc")], [], {}, "")
    assert any("Zhao Yun" in problem for problem in check_people(game, turn))
    fid = record_fact(game.world, zhao, "spared", game.player.id, place=None,
                      variant=make_variant("spared", zhao, game.player.id))
    game.world.upsert_belief(game.player.id, fid, make_variant("spared", zhao, game.player.id), None, 0.5, 2, "told")
    assert check_people(game, turn) == []


def test_the_knowledge_rule_catches_a_face_behind_a_mask(game):
    persona = game.world.add_entity("persona", "the Grey-Masked Swordsman", {"of": game.player.id})
    fid = record_fact(game.world, persona, "robbed", 999, place=None, variant=make_variant("robbed", persona, 999))
    assert check_knowledge(game.world) == []
    leaked = make_variant("robbed", game.player.id, 999)
    game.world.upsert_belief(12345, fid, leaked, None, 0.5, 2, "gossip")
    assert any("credited" in problem for problem in check_knowledge(game.world))


def test_a_lie_must_name_its_liar(game):
    with game.world.transaction():
        game.world.add_fact(1, "robbed", 2, is_true=False, data={"variant": make_variant("robbed", 1, 2)})
    assert any("lie" in problem for problem in check_knowledge(game.world))


def test_a_masked_killing_stays_with_the_mask(game, monkeypatch):
    for name in ("ART_CHANCE", "VOICE_CHANCE", "CHANGE_CHANCE"):
        monkeypatch.setattr(masks, name, 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "AVENGER_ROAD_CHANCE", 0.0)
    world, me = game.world, game.player.id
    with world.transaction():
        mask = world.add_entity("mask", "plain mask", {"persona": None})
        world.relate(me, mask, "owns")
    game.perform(Action("wear_mask"))
    persona = world.entity(me).data["masked"]
    victim = next(p for p in people_at(world, game.place.id, exclude=me))
    world.update_data(victim.id, traits=["proud", "honest"])
    game.perform(Action("challenge", victim.id))
    game.combat.stage, game.combat.harm = "verdict", {"player": 0.0, "opponent": 90.0}
    game.perform(Action("verdict", "kill"))
    game.perform(Action("remove_mask"))
    road = next(c.action for c in game.look().all_choices if c.action.verb == "travel" and "north" in c.label)
    game.perform(road)
    game.perform(Action("rest", 7))
    town = game.place.id
    rumours.catch_up(world, town)
    stranger = next(p for p in people_at(world, town, exclude=me) if not world.memories(p.id, about=me))
    assert reputation(world, town, persona).renown > 0
    assert reputation(world, town, me).renown == 0
    assert "killed" not in (attitude(world, stranger.id, me).reason or "")
    assert not any("renowned" in text or "known as" in text for text, _ in sheet_lines(world, me)
                   if text.startswith("  Here"))
    record_fact(world, persona, "is", me, place=town, variant=make_variant("is", persona, me))
    assert reputation(world, town, me).renown > 0
    assert "killed" in (attitude(world, stranger.id, me).reason or "")


def test_the_same_choices_make_the_same_world(tmp_path):
    digests = []
    for n in range(2):
        g = Game.new(tmp_path / f"d{n}.world", "Hero", world_seed=21, creation=CreationChoice("origin", "hunter"))
        turn = g.start()
        for step in range(40):
            turn = g.perform(turn.choices[(step * 7) % len(turn.choices)].action)
        digests.append(g.world.digest())
        g.close()
    assert digests[0] == digests[1]
