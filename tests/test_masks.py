import pytest

import systems.masks as masks
from engine.commands import parse
from engine.game import Action, Game
from systems.attitude import attitude
from systems.beliefs import knows_identity
from systems.creation import CreationChoice
from systems.purse import silver_of


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


@pytest.fixture
def unseen(monkeypatch):
    for name in ("ART_CHANCE", "VOICE_CHANCE", "CHANGE_CHANCE"):
        monkeypatch.setattr(masks, name, 0.0)


def person(game, name, traits=("kind", "honest"), occupation="innkeeper"):
    surname, given = name.split()
    pid = game.world.add_entity("person", name, {
        "occupation": occupation, "traits": list(traits), "realm": "mortal", "surname": surname, "given": given,
        "gender": "man", "age": 40, "portrait": {"hair": 0, "face": 0, "robe": 0}})
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def give_mask(game):
    with game.world.transaction():
        mask = game.world.add_entity("mask", "plain mask", {"persona": None})
        game.world.relate(game.player.id, mask, "owns")
    return mask


def win(game, npc, verdict):
    game.perform(Action("challenge", npc))
    game.combat.stage, game.combat.harm = "verdict", {"player": 0.0, "opponent": 90.0}
    return game.perform(Action("verdict", verdict))


def test_buying_a_mask_from_a_merchant(game):
    merchant = person(game, "Qian Duo", occupation="merchant")
    game.world.update_data(game.player.id, silver=20)
    turn = game.perform(Action("talk", merchant))
    assert "browse" in {c.action.verb for c in turn.all_choices}
    turn = game.perform(Action("browse"))
    buy = next(c for c in turn.choices if c.action.verb == "buy_mask")
    game.perform(buy.action)
    assert silver_of(game.world, game.player.id) == 15
    assert len(masks.masks_of(game.world, game.player.id)) == 1


def test_wearing_a_mask_makes_a_persona_that_sticks(game, unseen):
    give_mask(game)
    assert "wear_mask" in {c.action.verb for c in game.perform(Action("look")).all_choices}
    turn = game.perform(Action("wear_mask"))
    persona = game.world.entity(game.player.id).data["masked"]
    name = game.world.entity(persona).name
    assert name.startswith("the ") and "-Masked " in name
    assert "(masked)" in turn.status
    assert f"You are now {name}." in [text for text, _ in turn.lines]
    game.perform(Action("remove_mask"))
    assert "(masked)" not in game.perform(Action("look")).status
    game.perform(Action("wear_mask"))
    assert game.world.entity(game.player.id).data["masked"] == persona
    assert parse("wear mask", [], []) == Action("wear_mask")
    assert parse("remove mask", [], []) == Action("remove_mask")


def test_a_masked_player_is_greeted_as_a_stranger(game, unseen):
    friend = person(game, "Old Wu")
    for _ in range(3):
        game.perform(Action("talk", friend))
        game.perform(Action("farewell"))
    give_mask(game)
    game.perform(Action("wear_mask"))
    game.perform(Action("talk", friend))
    last = game.world.chronicle_about(game.player.id, limit=1)[0]
    assert last.kind == "met"
    assert last.data["as"] == game.world.entity(game.player.id).data["masked"]


def test_a_masked_robbery_is_credited_to_the_persona(game, unseen):
    victim = person(game, "Ma Bo", traits=("proud", "honest"))
    give_mask(game)
    game.perform(Action("wear_mask"))
    persona = game.world.entity(game.player.id).data["masked"]
    win(game, victim, "rob")
    assert game.world.facts(predicate="robbed")[0].subject == persona
    assert attitude(game.world, victim, game.player.id).word == "neutral"
    assert attitude(game.world, victim, persona).word == "wary"


def test_a_fighting_style_gives_the_wearer_away(game, monkeypatch):
    monkeypatch.setattr(masks, "ART_CHANCE", 1.0)
    monkeypatch.setattr(masks, "VOICE_CHANCE", 0.0)
    monkeypatch.setattr(masks, "CHANGE_CHANCE", 0.0)
    rival = person(game, "Iron Gu", traits=("proud", "honest"))
    win(game, rival, "spare")
    give_mask(game)
    game.perform(Action("wear_mask"))
    persona = game.world.entity(game.player.id).data["masked"]
    turn = win(game, rival, "spare")
    assert knows_identity(game.world, rival, persona)
    assert game.world.facts(predicate="is")[0].subject == persona
    assert any("Iron Gu looks hard at you" in text for text, _ in turn.lines)


def test_changing_in_public_can_be_seen(game, monkeypatch):
    monkeypatch.setattr(masks, "CHANGE_CHANCE", 1.0)
    friend = person(game, "Old Wu")
    game.perform(Action("talk", friend))
    game.perform(Action("farewell"))
    give_mask(game)
    label = next(c.label for c in game.perform(Action("look")).all_choices if c.action.verb == "wear_mask")
    assert label == "Wear your mask (1 here know your face)"
    game.perform(Action("wear_mask"))
    assert knows_identity(game.world, friend, game.world.entity(game.player.id).data["masked"])
