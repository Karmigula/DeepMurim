import json
import subprocess

from ai.backends import ClaudeCode, OpenCode, free_port, last_json, opencode_exe
from ai.bridge import PAUSE_AFTER, Job

PROSE = {"type": "object", "properties": {"prose": {"type": "string", "maxLength": 1500}}, "required": ["prose"],
         "additionalProperties": False}
NARRATE = Job("narrate", "claude-haiku-4-5", 10.0, PROSE, "Write prose.")
TALK = Job("intent", "claude-sonnet-5", 30.0, PROSE, "Interpret.", tools=True)


# --- Claude Code through the Agent SDK ------------------------------------------------------------------------------

class ResultMessage:
    def __init__(self, structured_output=None, result="", is_error=False, errors=None):
        self.structured_output, self.result, self.is_error, self.errors = structured_output, result, is_error, errors


class FakeClient:
    """Stands in for the SDK's ClaudeSDKClient: answers each query from a script."""
    made: list = []

    def __init__(self, options, script=None):
        self.options, self.script, self.sessions = options, list(script or []), []
        FakeClient.made.append(self)

    async def connect(self):
        pass

    async def disconnect(self):
        pass

    async def query(self, prompt, session_id="default"):
        self.sessions.append((session_id, prompt))

    async def receive_response(self):
        yield object()  # an assistant message first, as the SDK sends
        yield self.script.pop(0)


def claude(script, **kw):
    FakeClient.made = []
    return ClaudeCode(client_factory=lambda options: FakeClient(options, script), **kw)


def test_claude_code_answers_with_the_structured_reply_each_in_a_fresh_session():
    door = claude([ResultMessage({"prose": "Mist."}), ResultMessage({"prose": "Rain."})])
    assert door.call(NARRATE, "first") == {"prose": "Mist."}
    assert door.call(NARRATE, "second") == {"prose": "Rain."}
    [client] = FakeClient.made  # one client for the job, kept open
    assert [s for s, _ in client.sessions] == ["dm-1", "dm-2"]
    door.close()


def test_claude_code_runs_on_the_plan_never_an_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    door = claude([ResultMessage({"prose": "x"})], models={"narrate": "claude-sonnet-5"})
    door.call(NARRATE, "p")
    options = FakeClient.made[0].options
    assert "ANTHROPIC_API_KEY" not in options.env and options.model == "claude-sonnet-5"
    assert options.setting_sources == [] and options.tools == [] and options.mcp_servers == {}
    assert options.output_format == {"type": "json_schema", "schema": PROSE}
    door.close()


def test_claude_code_gives_tools_only_to_a_tooled_job_with_a_server():
    door = claude([ResultMessage({"prose": "x"}), ResultMessage({"prose": "y"})])
    door.mcp_url = "http://127.0.0.1:5000/mcp"
    door.call(NARRATE, "p")
    door.call(TALK, "q")
    prose, talk = FakeClient.made
    assert prose.options.mcp_servers == {} and prose.options.allowed_tools == []
    assert talk.options.mcp_servers == {"deepmurim": {"type": "http", "url": "http://127.0.0.1:5000/mcp"}}
    assert talk.options.allowed_tools == ["mcp__deepmurim__*"]
    door.close()


def test_claude_code_failures_are_none_and_a_logged_out_one_closes_the_door():
    door = claude([ResultMessage(is_error=True, result="Invalid API key · Please run /login"),
                   ResultMessage({"verse": "wrong shape"})])
    assert door.call(NARRATE, "p") is None
    assert door.available()[0] is False and "not logged in" in door.available()[1]
    door._checked = None
    assert door.call(NARRATE, "p") is None and door.exchanges[-1].error == "the reply did not fit its schema"
    door.close()


def test_claude_code_pauses_after_three_failures():
    door = claude([ResultMessage(is_error=True, result="overloaded")] * PAUSE_AFTER)
    for _ in range(PAUSE_AFTER):
        door.call(NARRATE, "p")
    assert door.paused() and door.just_paused
    door.close()


# --- OpenCode ---------------------------------------------------------------------------------------------------

EVENTS = [
    {"type": "step_start", "part": {}},
    {"type": "text", "part": {"type": "text", "text": "Here you go:\n```json\n{\"prose\": \"You climb the pass.\"}\n```"}},
    {"type": "step_finish", "part": {"tokens": {"input": 100669, "output": 168}, "cost": 0}},
]


def test_the_json_is_found_in_opencodes_last_text():
    assert last_json(EVENTS) == ({"prose": "You climb the pass."}, "")
    error = [{"type": "error", "error": {"name": "APIError", "data": {"message": "free tier only from OpenCode"}}}]
    assert last_json(error) == (None, "free tier only from OpenCode")
    assert last_json([{"type": "text", "part": {"text": "no braces"}}]) == (None, "no JSON in the reply")


def test_opencodes_exe_is_found_beside_its_shim_never_the_shim(tmp_path, monkeypatch):
    shim = tmp_path / "opencode.cmd"
    shim.write_text("@echo off")
    exe = tmp_path / "node_modules" / "opencode-ai" / "bin" / "opencode.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    monkeypatch.setattr("shutil.which", lambda name: str(shim) if name == "opencode.cmd" else None)
    assert opencode_exe() == str(exe)
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert opencode_exe() is None and OpenCode(exe=None).available() == (False, "OpenCode is not installed")


class Server:
    pid = 4321

    def __init__(self, *a, **kw):
        self.cmd, self.kw = a[0], kw

    def poll(self):
        return None


def test_opencode_warms_a_server_and_attaches_each_call(tmp_path, monkeypatch):
    calls = []

    def runner(cmd, **kw):
        calls.append((cmd, kw))
        return subprocess.CompletedProcess(cmd, 0, "\n".join(json.dumps(e) for e in EVENTS), "")
    servers = []

    def popen(cmd, **kw):
        servers.append(Server(cmd, **kw))
        return servers[-1]
    monkeypatch.setattr("socket.create_connection", lambda *a, **kw: __import__("contextlib").nullcontext())
    door = OpenCode(models={"narrate": "opencode/big-pickle"}, exe="opencode.exe", runner=runner, popen=popen,
                    workdir=tmp_path)
    door.mcp_url = "http://127.0.0.1:5000/mcp"
    assert door.call(NARRATE, "a misty pass") == {"prose": "You climb the pass."}
    assert door.call(NARRATE, "again") == {"prose": "You climb the pass."}
    assert len(servers) == 1 and servers[0].cmd[:2] == ["opencode.exe", "serve"]
    cmd = calls[0][0]
    assert cmd[:4] == ["opencode.exe", "run", "--attach", door.url] and cmd[cmd.index("-m") + 1] == "opencode/big-pickle"
    assert '"prose"' in cmd[-1] and "a misty pass" in cmd[-1]  # the schema rides in the message
    assert "Use no tools." in cmd[-1]  # prose needs none, though the server offers them
    written = json.loads((tmp_path / "opencode.json").read_text(encoding="utf-8"))
    assert written["mcp"]["deepmurim"] == {"type": "remote", "url": "http://127.0.0.1:5000/mcp", "enabled": True}


def test_opencodes_errors_are_none_and_remembered(tmp_path, monkeypatch):
    def runner(cmd, **kw):
        out = json.dumps({"type": "error", "error": {"data": {"message": "rate limited"}}})
        return subprocess.CompletedProcess(cmd, 1, out, "")
    monkeypatch.setattr("socket.create_connection", lambda *a, **kw: __import__("contextlib").nullcontext())
    door = OpenCode(exe="opencode.exe", runner=runner, popen=Server, workdir=tmp_path)
    assert door.call(NARRATE, "p") is None and door.exchanges[-1].error == "rate limited"


def test_a_free_port_is_a_port():
    assert 0 < free_port() < 65536
