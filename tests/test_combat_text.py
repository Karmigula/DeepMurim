import pytest

from engine.game import Game
from engine.journal import summarize
from narrate.brief import MAX_PROMPT, event_brief
from narrate.procedural import ProceduralNarrator
from systems.creation import CreationChoice
from world.events import Event


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    yield g
    g.close()


def opponent(game, beast=False):
    data = {"occupation": "grey wolf" if beast else "bandit", "traits": ["greedy"], "realm": "mortal",
            "beast": beast, "portrait": {"hair": 0, "face": 0, "robe": 0}}
    pid = game.world.add_entity("person", "a grey wolf" if beast else "Opp Ma", data)
    game.world.relate(pid, game.place.id, "located_in")
    return pid


def exchange(game, opp, **changes):
    data = {
        "duel": 1, "n": 1, "player_intent": "strike", "opponent_intent": "guard", "player_output": "steady",
        "opponent_output": "steady", "player_output_choice": "steady", "player_technique": None,
        "player_technique_name": "Pale Crane Palm", "opponent_technique_name": "Iron Tiger Fist",
        "blows": [{"target": "opponent", "damage": 20.0, "wound": ["left arm", "cut", 2]},
                  {"target": "player", "damage": 10.0, "wound": None}],
        "openings": [], "reveals": [], "recover": [], "tendency": None, "qi_spent": {"player": 3, "opponent": 3},
        "deviation_added": 0.0, "fled": None, "gave_up": None, "fragment": None, "stage": "fighting",
        "harm_after": {"player": 10.0, "opponent": 20.0},
    }
    data.update(changes)
    return Event("exchange", (game.player.id, opp), game.place.id, data)


def ended(game, opp, **changes):
    data = {"duel": 1, "mode": "duel", "result": "won", "reason": "broken", "verdict": "rob", "by": "player",
            "silver": 12, "crippled": None, "loot": [99], "insight": 1.0, "life_and_death": False,
            "fragment": None, "purpose": {}}
    data.update(changes)
    return Event("duel_ended", (game.player.id, opp), game.place.id, data)


def test_an_exchange_is_told_plainly(game):
    brief = event_brief(game.world, 1, exchange(game, opponent(game)))
    assert brief.outcome == (
        "You strike; Opp Ma guards.",
        "Your Pale Crane Palm lands on their left arm.",
        "Opp Ma's Iron Tiger Fist catches you.",
        "You are fresh; Opp Ma is bruised.",
    )
    assert len(brief.to_prompt()) <= MAX_PROMPT and brief.other.name == "Opp Ma"


def test_fleeing_yielding_and_beasts(game):
    opp = opponent(game)
    assert event_brief(game.world, 2, exchange(game, opp, fled=True, blows=[])).outcome[0] == "You break away and escape."
    assert event_brief(game.world, 3, exchange(game, opp, gave_up="yield", blows=[])).outcome[0] == "Opp Ma lowers their guard and yields."
    wolf = opponent(game, beast=True)
    lines = event_brief(game.world, 4, exchange(game, wolf, opponent_technique_name=None)).outcome
    assert lines[2] == "A grey wolf's claws catch you."


def test_endings_and_their_grammar(game):
    opp = opponent(game)
    won = event_brief(game.world, 5, ended(game, opp))
    assert won.outcome[:2] == ("You have beaten Opp Ma.", "You take 12 silver and 1 manual.")
    assert won.details["grammar_key"] == "duel_ended.won"
    assert ProceduralNarrator().narrate(won)[0][1] == "gold"
    lost = event_brief(game.world, 6, ended(game, opp, result="lost", by="opponent", verdict="cripple",
                                           silver=0, loot=[], crippled=["Liver", "meridian"]))
    assert "They cripple your Liver meridian for good." in lost.outcome
    assert lost.details["grammar_key"] == "duel_ended.lost"


def test_duel_journal_lines(game):
    opp = opponent(game)
    game.world.append_chronicle("duel_ended", (game.player.id, opp), game.place.id, ended(game, opp).data, 1.0)
    assert summarize(game.world, game.world.chronicle_about(game.player.id, limit=1)[0]).endswith("Beat Opp Ma.")
