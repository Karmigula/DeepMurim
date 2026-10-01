"""One real round trip through `claude -p` (phase 6 spec 11). Marked `live` and needs DEEPMURIM_LIVE=1."""
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
