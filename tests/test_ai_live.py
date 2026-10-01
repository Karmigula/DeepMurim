"""One real round trip through `claude -p` (phase 6 spec 11). Marked `live` and needs DEEPMURIM_LIVE=1."""
import os

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
    assert reply is not None and 0 < len(reply["prose"]) <= 900, list(bridge.exchanges)[-1].error
