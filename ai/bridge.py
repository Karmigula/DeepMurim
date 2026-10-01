"""The one door to Claude (phase 6 spec 2, 8): `claude -p` run once per request, its reply checked against a schema.

Every failure (no CLI, logged out, offline, a timeout, bad JSON, a reply that does not fit) returns None, and the
caller keeps its procedural text. Three failures in a row pause the door for five minutes.

The CLI is run stripped bare (plan ruling 2): no settings, skills, hooks or MCP servers of the user's own, no
built-in tools, and low effort, so a prose call costs about a thousand tokens and a few seconds instead of the
whole of the user's setup.
"""

import json
import os
import shutil
import subprocess
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

PAUSE_AFTER, PAUSE_SECONDS = 3, 300.0
KEPT = 20  # exchanges remembered for the debug overlay and bug reports
FIND = "find"  # Bridge(cli=FIND): look the claude command up on PATH; cli=None: there is none


@dataclass(frozen=True)
class Job:
    """One kind of request: which model, how long to wait, what shape the reply must have."""
    name: str
    model: str
    timeout: float
    schema: dict
    system: str
    tools: bool = False  # the read-only DeepMurim MCP tools (phase 6 spec 5); never for prose
    thinking: bool = False  # extended thinking: off for prose (it made one sentence cost 10-30 s; plan ruling 2)


@dataclass
class Exchange:
    job: str
    prompt: str
    reply: dict | None
    error: str = ""
    seconds: float = 0.0
    at: float = field(default_factory=time.time)


def conforms(schema: dict, value) -> bool:
    """A small JSON Schema check: types, required keys, no extra keys where forbidden, enums, string length."""
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(value, dict):
            return False
        props = schema.get("properties", {})
        if any(key not in value for key in schema.get("required", ())):
            return False
        if schema.get("additionalProperties") is False and any(key not in props for key in value):
            return False
        return all(conforms(props[key], v) for key, v in value.items() if key in props)
    if kind == "array":
        return isinstance(value, list) and all(conforms(schema.get("items", {}), v) for v in value) \
            and len(value) <= schema.get("maxItems", len(value))
    if kind == "string":
        return isinstance(value, str) and len(value) <= schema.get("maxLength", len(value)) \
            and ("enum" not in schema or value in schema["enum"])
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "boolean":
        return isinstance(value, bool)
    return True


class Bridge:
    def __init__(self, cli: str | None = FIND, runner=subprocess.run, mcp_config: Path | None = None,
                 clock=time.monotonic) -> None:
        self.cli = shutil.which("claude") if cli == FIND else cli
        self.runner = runner
        self.mcp_config = mcp_config  # written per save by ai.mcp_config (phase 6a Task 3)
        self.clock = clock
        self.failures = 0
        self.paused_until = 0.0
        self.just_paused = False  # set once when the pause begins: the log says so in one line
        self.exchanges: deque[Exchange] = deque(maxlen=KEPT)
        self._checked: tuple[bool, str] | None = None

    def available(self) -> tuple[bool, str]:
        """Whether the CLI answers at all (checked once): (yes, '') or (no, the reason)."""
        if self._checked is None:
            if not self.cli:
                self._checked = (False, "the claude command is not installed")
            else:
                try:
                    done = self.runner([self.cli, "--version"], capture_output=True, text=True, timeout=15)
                    ok = done.returncode == 0
                    self._checked = (ok, "" if ok else (done.stderr or "claude --version failed").strip()[:120])
                except (OSError, subprocess.SubprocessError) as exc:
                    self._checked = (False, f"claude did not start ({exc.__class__.__name__})")
        return self._checked

    def paused(self) -> bool:
        return self.clock() < self.paused_until

    def command(self, job: Job) -> list[str]:
        cmd = [self.cli or "claude", "-p", "--model", job.model, "--output-format", "json",
               "--json-schema", json.dumps(job.schema), "--system-prompt", job.system,
               "--no-session-persistence", "--setting-sources", "", "--disable-slash-commands",
               "--effort", "low", "--tools", "", "--strict-mcp-config"]
        if job.tools and self.mcp_config is not None:
            cmd += ["--mcp-config", str(self.mcp_config), "--allowedTools", "mcp__deepmurim__*"]
        else:
            cmd += ["--mcp-config", json.dumps({"mcpServers": {}})]
        return cmd

    @staticmethod
    def env(job: Job) -> dict:
        return {**os.environ, "MAX_THINKING_TOKENS": "0"} if not job.thinking else dict(os.environ)

    def call(self, job: Job, prompt: str) -> dict | None:
        """Claude's reply to this prompt, fitted to the job's schema; or None, and the caller carries on."""
        if self.paused() or not self.available()[0]:
            return None
        start = self.clock()
        reply, error = None, ""
        try:
            done = self.runner(self.command(job), input=prompt, capture_output=True, text=True, encoding="utf-8",
                               timeout=job.timeout, env=self.env(job))
            reply, error = self._parse(job, done)
        except subprocess.TimeoutExpired:
            error = f"no reply within {job.timeout:.0f} s"
        except (OSError, subprocess.SubprocessError) as exc:
            error = f"claude did not run ({exc.__class__.__name__})"
        self.exchanges.append(Exchange(job.name, prompt, reply, error, round(self.clock() - start, 2)))
        self._count(reply is not None)
        return reply

    @staticmethod
    def _parse(job: Job, done) -> tuple[dict | None, str]:
        if done.returncode != 0:
            return None, (done.stderr or f"exit {done.returncode}").strip()[:200]
        try:
            outer = json.loads(done.stdout)
        except ValueError:
            return None, "the reply was not JSON"
        if not isinstance(outer, dict) or outer.get("is_error"):
            return None, str(outer.get("result", "an error") if isinstance(outer, dict) else "an odd reply")[:200]
        reply = outer.get("structured_output")
        if reply is None:
            try:
                reply = json.loads(outer.get("result") or "")
            except ValueError:
                return None, "no structured reply"
        if not conforms(job.schema, reply):
            return None, "the reply did not fit its schema"
        return reply, ""

    def _count(self, ok: bool) -> None:
        if ok:
            self.failures = 0
            return
        self.failures += 1
        if self.failures >= PAUSE_AFTER:
            self.failures = 0
            self.paused_until = self.clock() + PAUSE_SECONDS
            self.just_paused = True
