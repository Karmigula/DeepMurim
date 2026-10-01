import json
import subprocess

from ai.bridge import PAUSE_AFTER, PAUSE_SECONDS, Bridge, Job, conforms
from ai.fake import FakeClaude

PROSE = {"type": "object", "properties": {"prose": {"type": "string", "maxLength": 600}}, "required": ["prose"],
         "additionalProperties": False}
JOB = Job("narrate", "claude-haiku-4-5", 8.0, PROSE, "Write prose.")
TOOLED = Job("intent", "claude-sonnet-5", 30.0, PROSE, "Interpret.", tools=True)


class Runner:
    """Stands in for subprocess.run: answers `--version`, then each request from its script."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def __call__(self, cmd, **kw):
        self.calls.append((cmd, kw))
        if cmd[1:] == ["--version"]:
            return subprocess.CompletedProcess(cmd, 0, "2.1.286 (Claude Code)", "")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        code, out = outcome
        return subprocess.CompletedProcess(cmd, code, out, "boom" if code else "")


def ok(reply: dict) -> tuple[int, str]:
    return 0, json.dumps({"type": "result", "is_error": False, "result": json.dumps(reply), "structured_output": reply})


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_a_reply_that_fits_its_schema_comes_back():
    runner = Runner(ok({"prose": "Mist curls over the pass."}))
    bridge = Bridge(cli="claude", runner=runner)
    assert bridge.call(JOB, "a brief") == {"prose": "Mist curls over the pass."}
    cmd, kw = runner.calls[-1]
    assert kw["input"] == "a brief" and kw["timeout"] == 8.0 and kw["env"]["MAX_THINKING_TOKENS"] == "0"
    assert cmd[:4] == ["claude", "-p", "--model", "claude-haiku-4-5"]
    assert json.loads(cmd[cmd.index("--json-schema") + 1]) == PROSE


def test_the_call_is_stripped_bare_and_tools_only_when_asked(tmp_path):
    runner = Runner(ok({"prose": "a"}), ok({"prose": "b"}))
    config = tmp_path / "deepmurim.json"
    bridge = Bridge(cli="claude", runner=runner, mcp_config=config)
    bridge.call(JOB, "x")
    bridge.call(TOOLED, "y")
    plain, tooled = runner.calls[1][0], runner.calls[2][0]
    for cmd in (plain, tooled):
        for flag in ("--setting-sources", "--disable-slash-commands", "--no-session-persistence", "--strict-mcp-config"):
            assert flag in cmd, flag
        assert cmd[cmd.index("--tools") + 1] == "" and cmd[cmd.index("--effort") + 1] == "low"
    assert "--allowedTools" not in plain and json.loads(plain[plain.index("--mcp-config") + 1]) == {"mcpServers": {}}
    assert tooled[tooled.index("--mcp-config") + 1] == str(config)
    assert tooled[tooled.index("--allowedTools") + 1] == "mcp__deepmurim__*"


def test_every_failure_is_none_and_remembered():
    runner = Runner((1, ""), (0, "not json"), ok({"verse": "wrong shape"}), subprocess.TimeoutExpired("claude", 8),
                    (0, json.dumps({"is_error": True, "result": "rate limited"})))
    bridge = Bridge(cli="claude", runner=runner)
    results = []
    for _ in range(5):
        bridge.paused_until = 0.0  # the pause is tested on its own
        results.append(bridge.call(JOB, "x"))
    assert results == [None] * 5
    errors = [e.error for e in bridge.exchanges]
    assert errors == ["boom", "the reply was not JSON", "the reply did not fit its schema", "no reply within 8 s",
                      "rate limited"]


def test_no_cli_means_no_call():
    runner = Runner()
    bridge = Bridge(cli=None, runner=runner)
    assert bridge.available() == (False, "the claude command is not installed")
    assert bridge.call(JOB, "x") is None and runner.calls == []


def test_three_failures_in_a_row_pause_the_door_for_five_minutes():
    clock = Clock()
    runner = Runner(*([(1, "")] * PAUSE_AFTER), ok({"prose": "back"}))
    bridge = Bridge(cli="claude", runner=runner, clock=clock)
    for _ in range(PAUSE_AFTER):
        assert bridge.call(JOB, "x") is None
    assert bridge.paused() and bridge.just_paused
    assert bridge.call(JOB, "x") is None and len(runner.calls) == 1 + PAUSE_AFTER  # not even tried
    clock.now += PAUSE_SECONDS + 1
    assert bridge.call(JOB, "x") == {"prose": "back"} and bridge.failures == 0


def test_a_success_between_failures_resets_the_count():
    runner = Runner((1, ""), (1, ""), ok({"prose": "fine"}), (1, ""), (1, ""))
    bridge = Bridge(cli="claude", runner=runner)
    for _ in range(5):
        bridge.call(JOB, "x")
    assert not bridge.paused() and bridge.failures == 2


def test_thinking_is_off_unless_the_job_asks_for_it():
    thinking = Job("intent", "claude-sonnet-5", 30.0, PROSE, "Think.", thinking=True)
    assert Bridge.env(JOB)["MAX_THINKING_TOKENS"] == "0"
    assert "MAX_THINKING_TOKENS" not in Bridge.env(thinking) or Bridge.env(thinking)["MAX_THINKING_TOKENS"] != "0"


def test_the_schema_check():
    schema = {"type": "object", "properties": {"kind": {"type": "string", "enum": ["pay", "give"]},
                                               "amount": {"type": "integer"},
                                               "items": {"type": "array", "items": {"type": "string"}, "maxItems": 2}},
              "required": ["kind"], "additionalProperties": False}
    assert conforms(schema, {"kind": "pay", "amount": 3, "items": ["a"]})
    assert not conforms(schema, {"kind": "steal"})
    assert not conforms(schema, {"kind": "pay", "amount": True})
    assert not conforms(schema, {"kind": "pay", "items": ["a", "b", "c"]})
    assert not conforms(schema, {"kind": "pay", "extra": 1})
    assert not conforms(schema, {})
    assert not conforms(PROSE, {"prose": "x" * 601})


def test_fake_claude_scripts_replies_and_failures():
    fake = FakeClaude({"prose": "one"}, None, lambda job, prompt: {"prose": prompt.upper()}, {"wrong": 1})
    assert fake.call(JOB, "a") == {"prose": "one"}
    assert fake.call(JOB, "b") is None
    assert fake.call(JOB, "c") == {"prose": "C"}
    assert fake.call(JOB, "d") is None  # does not fit its schema
    assert fake.call(JOB, "e") is None  # the script ran out
    assert [c[1] for c in fake.calls] == ["a", "b", "c", "d", "e"]
    assert FakeClaude(available=False).available()[0] is False
