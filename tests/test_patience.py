"""NPCs lose patience with repeated questions, and remember that they did."""

import pytest

from engine.game import Action, Game
from narrate.procedural import ProceduralNarrator
from systems.talk import patience_of


@pytest.fixture
def game(tmp_path):
    g = Game.new(tmp_path / "g.world", "Hero", world_seed=42)
    g.start()
    yield g
    g.close()


def npc_with(game, traits):
    npc = next(c.action.target for c in game.look().all_choices if c.action.verb == "talk")
    game.world.update_data(npc, traits=traits)
    return npc


def ask_until_it_ends(game, npc, limit=10):
    """Talk, then ask about work repeatedly; return how many asks it took to end the talk."""
    game.perform(Action("talk", npc))
    for n in range(1, limit + 1):
        game.perform(Action("ask", "work"))
        if game.focus is None:
            return n
    return None


def test_patience_depends_on_temper(game):
    assert patience_of(game.world.entity(npc_with(game, ["cautious", "honest"]))) == 3
    assert patience_of(game.world.entity(npc_with(game, ["hot-tempered", "proud"]))) == 2
    assert patience_of(game.world.entity(npc_with(game, ["kind", "lazy"]))) == 4


@pytest.mark.parametrize("traits, asks", [
    (["cautious", "honest"], 5),       # 1 real question + 3 tolerated repeats, the 4th repeat ends it
    (["hot-tempered", "proud"], 4),
    (["kind", "lazy"], 6),
])
def test_repeats_end_the_conversation(game, traits, asks):
    npc = npc_with(game, traits)
    assert ask_until_it_ends(game, npc) == asks
    assert game.world.chronicle_about(npc, limit=1)[0].kind == "lost_patience"
    assert game.world.memories(npc)[-1].feeling == "annoyed"


def test_switching_questions_still_counts_repeats(game):
    npc = npc_with(game, ["cautious", "honest"])
    game.perform(Action("talk", npc))
    for topic in ["work", "town", "work", "town", "work"]:  # 3 repeats: still talking
        game.perform(Action("ask", topic))
    assert game.focus == npc
    game.perform(Action("ask", "town"))  # 4th repeat
    assert game.focus is None


def test_next_conversation_starts_fresh_but_cool(game, tmp_path):
    npc = npc_with(game, ["cautious", "honest"])
    ask_until_it_ends(game, npc)
    game.perform(Action("talk", npc))
    greeting = game.last_briefs[0]
    assert greeting.details["annoyed_last_time"] == "yes"
    name = game.world.entity(npc).name
    assert greeting.facts[0] == f"Last time, {name} lost patience with your repeated questions."
    assert ProceduralNarrator()._key(greeting) == "conversed.annoyed"
    game.perform(Action("ask", "work"))  # a fresh conversation: one question is fine
    assert game.focus == npc
    assert game.last_briefs[0].details["asked_before"]  # they still remember being asked

    game.perform(Action("farewell"))
    game.perform(Action("talk", npc))  # the calm conversation in between clears 'last time'
    later = game.last_briefs[0]
    assert "annoyed_last_time" not in later.details
    assert f"{name} once lost patience with your repeated questions." in later.facts


def test_journal_and_reload_remember_it(game):
    npc = npc_with(game, ["cautious", "honest"])
    ask_until_it_ends(game, npc)
    lines = [text for text, _ in game.perform(Action("journal")).lines]
    assert any("lost patience" in line for line in lines)
    path = game.world.path
    game.close()
    reloaded = Game.load(path)
    reloaded.perform(Action("talk", npc))
    assert reloaded.last_briefs[0].details["annoyed_last_time"] == "yes"
    reloaded.close()
    game.world = Game.load(path).world  # let the fixture's close() succeed
