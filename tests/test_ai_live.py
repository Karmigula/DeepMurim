"""Real round trips (phase 6 spec 11, 13.7, 14.9): prose, typed actions and talk. Marked `live`; needs DEEPMURIM_LIVE=1."""
import os
from pathlib import Path

import pytest

from ai.bridge import Bridge
from ai.narrate import narrate_job

pytestmark = [pytest.mark.live,
              pytest.mark.skipif(os.environ.get("DEEPMURIM_LIVE") != "1", reason="set DEEPMURIM_LIVE=1 to call Claude")]


def test_claude_writes_a_line_of_prose():
    bridge = Bridge()
    if not bridge.available()[0]:
        pytest.skip(bridge.available()[1])
    reply = bridge.call(narrate_job(), "STATE:\n- a misty marsh town at dawn\n\nTHIS TURN:\nEVENT: look\nOUTCOME:\n- You look around.")
    assert reply is not None and 0 < len(reply["prose"]) <= 1500, list(bridge.exchanges)[-1].error


PROMPT = "STATE:\n- a misty marsh town at dawn\n\nTHIS TURN:\nEVENT: look\nOUTCOME:\n- You look around."


def test_claude_code_writes_a_paragraph_through_the_agent_sdk():
    from ai.backends import ClaudeCode
    door = ClaudeCode()
    if not door.available()[0]:
        pytest.skip(door.available()[1])
    try:
        reply = door.call(narrate_job(), PROMPT)
    finally:
        door.close()
    assert reply is not None and 0 < len(reply["prose"]) <= 1500, list(door.exchanges)[-1].error


def test_opencode_writes_a_paragraph_with_a_free_model():
    from ai.backends import OpenCode, opencode_exe
    from ai.models import OpenCodeModels
    exe = opencode_exe()
    if exe is None:
        pytest.skip("OpenCode is not installed")
    free = OpenCodeModels(exe).free()
    if not free:
        pytest.skip("OpenCode offers no free model")
    door = OpenCode(models={"narrate": free[0]}, workdir=Path("logs") / "live-opencode")  # never under Temp
    try:
        reply = door.call(narrate_job(timeout=120.0), PROMPT)
    finally:
        door.close()
    assert reply is not None and 0 < len(reply["prose"]) <= 1500, list(door.exchanges)[-1].error


def a_game(tmp_path, monkeypatch):
    import systems.encounters as encounters
    from engine.game import Game
    from systems.creation import CreationChoice
    monkeypatch.setattr(encounters, "CHALLENGE_CHANCE", 0.0)
    monkeypatch.setattr(encounters, "ENCOUNTER_CHANCE", 0.0)
    game = Game.new(tmp_path / "live.world", "Hero", world_seed=11, creation=CreationChoice("origin", "hunter"))
    game.start()
    return game


def typed_round_trips(door, game, timeout):
    """One typed action and one line of talk (6c): each answered in its shape, its proposals weighed."""
    from ai.intent import dialogue_job, dialogue_prompt, intent_job, intent_prompt
    from ai.validate import DIALOGUE_KINDS, Scene, accept
    from world.gen.materialize import people_at
    person = people_at(game.world, game.place.id, exclude=game.player.id)[0]
    scene = Scene(game.world, game.player.id, game.place.id, [], "live")
    acted = door.call(intent_job(timeout), intent_prompt(game, "I sit by the well and listen to the gossip.", [], []))
    assert acted is not None and acted["prose"], list(door.exchanges)[-1].error
    accept(scene, acted["proposals"])
    said = door.call(dialogue_job(timeout), dialogue_prompt(game, "What news of the roads?", person.id, [], []))
    assert said is not None and said["reply"] and said["summary"], list(door.exchanges)[-1].error
    accept(scene, said["proposals"], DIALOGUE_KINDS)


def test_claude_code_answers_a_typed_action_and_a_line_of_talk(tmp_path, monkeypatch):
    from ai.backends import ClaudeCode
    door = ClaudeCode()
    if not door.available()[0]:
        pytest.skip(door.available()[1])
    game = a_game(tmp_path, monkeypatch)
    try:
        typed_round_trips(door, game, 60.0)
    finally:
        door.close()
        game.close()


def test_opencode_answers_a_typed_action_and_a_line_of_talk(tmp_path, monkeypatch):
    from ai.backends import OpenCode, opencode_exe
    from ai.models import OpenCodeModels
    exe = opencode_exe()
    if exe is None:
        pytest.skip("OpenCode is not installed")
    free = OpenCodeModels(exe).free()
    if not free:
        pytest.skip("OpenCode offers no free model")
    door = OpenCode(models={"intent": free[0], "dialogue": free[0]}, workdir=Path("logs") / "live-opencode")
    game = a_game(tmp_path, monkeypatch)
    try:
        typed_round_trips(door, game, 150.0)
    finally:
        door.close()
        game.close()
