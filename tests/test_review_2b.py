"""Findings from the phase 2b final review."""

import pytest

import systems.encounters as encounters
from engine.game import Action, Game
from narrate.brief import event_brief
from systems.creation import CreationChoice
from world.events import Event, Witness, commit


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    g.start()
    yield g
    g.close()


def hothead(game, feeling):
    pid = game.world.add_entity("person", "Hot Wu", {"occupation": "constable", "traits": ["hot-tempered"],
                                                    "realm": "mortal", "portrait": {"hair": 0, "face": 0, "robe": 0}})
    game.world.relate(pid, game.place.id, "located_in")
    commit(game.world, [Event("parted", (game.player.id, pid), game.place.id, {}, witnesses=(Witness(pid, feeling, 0.5),))])
    return pid


def test_a_declined_challenge_does_not_return_at_once(game, monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 1.0)
    npc = hothead(game, "annoyed")
    game.world.set_time(game.world.time + 4)
    game.perform(Action("look"))
    assert game.challenger == npc
    game.perform(Action("answer_challenge", False))
    game.perform(Action("look"))
    assert game.challenger is None


def test_contempt_alone_is_not_a_grudge(game, monkeypatch):
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 1.0)
    hothead(game, "contempt")
    game.world.set_time(game.world.time + 4)
    game.perform(Action("look"))
    assert game.challenger is None


def test_reading_a_style_and_glimpsing_a_fragment_both_show(game):
    opp = game.world.add_entity("person", "Opp Ma", {"occupation": "bandit", "traits": ["cunning"], "realm": "mortal"})
    data = {
        "duel": 1, "n": 1, "player_intent": "probe", "opponent_intent": "feint", "player_output": "steady",
        "opponent_output": "steady", "player_output_choice": "steady", "player_technique": None,
        "player_technique_name": "Pale Crane Palm", "opponent_technique_name": "Iron Tiger Fist",
        "blows": [{"target": "opponent", "damage": 12.0, "wound": ["torso", "bruise", 2]}],
        "openings": [], "reveals": ["player"], "recover": [], "tendency": "feints and tricks",
        "qi_spent": {"player": 3, "opponent": 3}, "deviation_added": 0.0, "fled": None, "gave_up": None,
        "fragment": {"technique": "Iron Tiger Fist", "form": "fist", "element": "metal", "segment": ["Lung", "Heart"]},
        "stage": "fighting", "harm_after": {"player": 0.0, "opponent": 12.0},
    }
    outcome = event_brief(game.world, 1, Event("exchange", (game.player.id, opp), game.place.id, data)).outcome
    joined = " ".join(outcome)
    assert "feints and tricks" in joined and "glimpse something of the Iron Tiger Fist" in joined
