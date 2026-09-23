import pytest

import systems.encounters as encounters
from engine.game import Action, Game
from engine.sheet import sheet_lines
from systems.creation import CreationChoice
from systems.facts import make_variant, record_fact
from world.events import Event, Witness, commit
from world.gen.materialize import ensure_town


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def person(game, name, traits=("curious", "lazy"), occupation="innkeeper"):
    surname, given = name.split()
    pid = game.world.add_entity("person", name, {
        "occupation": occupation, "traits": list(traits), "realm": "mortal", "surname": surname, "given": given,
        "gender": "man", "age": 40, "portrait": {"hair": 0, "face": 0, "robe": 0}})
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def hate(game, npc):
    commit(game.world, [Event("insulted", (game.player.id, npc), game.place.id, {},
                              witnesses=(Witness(npc, "hatred", 1.0),))])


def bandit_kills(game, place):
    for name in ("Ma Bo", "Ma Da", "Ma San"):
        bandit = person(game, name, occupation="bandit")
        record_fact(game.world, game.player.id, "killed", bandit, place=place,
                    variant=make_variant("killed", game.player.id, bandit, place=game.world.entity(place).name,
                                         form="fist"))


def test_a_hostile_greeting_says_why(game):
    npc = person(game, "Old Wu")
    hate(game, npc)
    turn = game.perform(Action("talk", npc))
    assert "Old Wu seems hostile toward you (you wronged them)." in [text for text, _ in turn.lines]
    brief = game.last_briefs[0]
    assert brief.facts[0] == "Old Wu is hostile toward you: you wronged them."
    assert game.narrator._key(brief) == "met.hostile"


def test_a_stranger_is_greeted_as_before(game):
    turn = game.perform(Action("talk", person(game, "Hu Mei")))
    assert not any("seems" in text for text, _ in turn.lines)


def test_hostile_people_lose_patience_sooner(game):
    calm, cross = person(game, "Hu Mei"), person(game, "Old Wu")
    hate(game, cross)
    for npc, keeps_talking in ((calm, True), (cross, False)):
        game.perform(Action("talk", npc))
        for _ in range(4):
            game.perform(Action("ask", "work"))
        assert (game.focus == npc) is keeps_talking
        if game.focus is not None:
            game.perform(Action("farewell"))


def test_the_sheet_shows_reputation(game):
    bandit_kills(game, game.place.id)
    text = [line for line, _ in sheet_lines(game.world, game.player.id)]
    assert "Reputation:" in text
    assert any(line.startswith(f"  Here in {game.place.name}: renowned, righteous, known as the ") for line in text)


def test_arriving_somewhere_that_knows_you(game, monkeypatch):
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
    road = next(c.action for c in game.start().all_choices if c.action.verb == "travel" and "north" in c.label)
    town = ensure_town(game.world, *road.target)
    bandit_kills(game, town)
    turn = game.perform(road)
    assert any(text.startswith("People here know you as the ") for text, _ in turn.lines)
    scene = next(b for b in game.last_briefs if b.kind == "scene")
    assert any("know you as the" in fact for fact in scene.facts)
