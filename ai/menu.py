"""The AI menu (phase 6 spec 13.2-13.3), opened with F1: the mode, the backend, the models, and the Connect page.

Pure state: it reads and changes the settings (`Config.ai_mode`, `ai_backend`, `ai_models`) and says what changed;
the App applies it (a new backend, the mode's own rules) and saves.
"""

import os
import shutil

from ai.backends import ClaudeCode, OpenCode, opencode_exe
from ai.models import CLAUDE_DEFAULTS, CLAUDE_MODELS, OPENCODE_DEFAULT, OpenCodeModels, label

BACKENDS = (("claude_code", "Claude Code"), ("opencode", "OpenCode"))
MODES = ("off", "assist", "ai_only")
MODE_NAMES = {"off": "off", "assist": "assist (the engine's words first, then the model's)",
              "ai_only": "AI only (only the model's words)"}
ROLES = (("narrate", "Prose model"), ("talk", "Typed actions and talk (6c)"))


def chosen(config, backend: str | None = None) -> dict:
    """The models chosen for a backend: {'narrate': ..., 'talk': ...}, defaults filled in. Only what the menu would
    offer is chosen (a hand-edited settings file names no other): Claude Code's three, OpenCode's own provider (and
    of that, `OpenCode` itself runs only the free ones)."""
    backend = backend or config.ai_backend
    picked = dict((config.ai_models or {}).get(backend, {}))
    if backend == "opencode":
        return {role: m if isinstance(m := picked.get(role), str) and m.startswith("opencode/") else OPENCODE_DEFAULT
                for role in ("narrate", "talk")}
    offered = dict(CLAUDE_MODELS)
    return {role: picked[role] if picked.get(role) in offered else CLAUDE_DEFAULTS[role] for role in ("narrate", "talk")}


def make_backend(config, workdir=None, opencode_models: OpenCodeModels | None = None):
    """The backend the settings name, with its models per job."""
    models = chosen(config)
    per_job = {"narrate": models["narrate"], "intent": models["talk"], "dialogue": models["talk"]}
    if config.ai_backend == "opencode":
        return OpenCode(models=per_job, workdir=workdir,
                        free_models=opencode_models.free if opencode_models is not None else None)
    return ClaudeCode(models=per_job)


def connect_lines(mcp_url: str | None, why: str | None = None) -> list:
    """How to reach the models, and how to reach DeepMurim from them (spec 13.3)."""
    claude, exe = shutil.which("claude"), opencode_exe()
    lines = [("Connect", "heading")]
    if why:
        lines.append((f"  The chosen backend cannot be used: {why}.", "red"))
    lines += [
             (f"  Claude Code: {'installed' if claude else 'not installed (claude.com/claude-code)'}", "default")]
    if claude:
        lines.append(("    Uses your own Claude login (your Pro/Max plan). Sign in once by running `claude` and "
                      "typing /login.", "dim"))
    if os.environ.get("ANTHROPIC_API_KEY"):
        lines.append(("    Warning: ANTHROPIC_API_KEY is set on this machine. DeepMurim leaves it out, so your plan "
                      "is used, but other Claude Code sessions will bill the API.", "red"))
    lines.append((f"  OpenCode: {'installed' if exe else 'not installed (opencode.ai)'}", "default"))
    if exe:
        lines.append(("    DeepMurim lists only OpenCode's free models. Sign in with `opencode auth login` if a "
                      "model asks for it.", "dim"))
    lines += [("", "default"), ("DeepMurim's MCP server (the world as you know it, read-only)", "heading")]
    if mcp_url:
        lines += [(f"  Running at {mcp_url}", "default"),
                  ("  To use it from your own Claude Code session:", "dim"),
                  (f"    claude mcp add --transport http deepmurim {mcp_url}", "default"),
                  ("  From OpenCode, add to opencode.json:", "dim"),
                  (f'    "mcp": {{"deepmurim": {{"type": "remote", "url": "{mcp_url}"}}}}', "default")]
    else:
        lines.append(("  Not running: it starts when the AI is on (mode assist or AI only).", "dim"))
    return lines


class AiMenu:
    def __init__(self, config, opencode_models: OpenCodeModels | None = None, mcp_url=None, why=None) -> None:
        self.config = config
        self.page = "main"
        self.opencode = opencode_models or OpenCodeModels(opencode_exe())
        self.mcp_url = mcp_url  # a callable: the server's address now, or None
        self.why = why  # a callable: why the chosen backend cannot be used now, or None

    def models(self, backend: str) -> list[str]:
        if backend == "opencode":
            return self.opencode.known() or [OPENCODE_DEFAULT]  # never waits: the list is read on its own thread
        return [m for m, _ in CLAUDE_MODELS]

    def _why(self) -> str | None:
        return self.why() if callable(self.why) else self.why

    def choices(self) -> list[str]:
        if self.page == "connect":
            return ["Back"]
        c, backend = self.config, self.config.ai_backend
        models = chosen(c)
        return [f"Mode: {c.ai_mode}", f"Backend: {dict(BACKENDS)[backend]}"] + \
            [f"{name}: {label(backend, models[role])}" for role, name in ROLES] + ["Connect...", "Close"]

    def lines(self) -> list:
        if self.page == "connect":
            return connect_lines(self.mcp_url() if callable(self.mcp_url) else self.mcp_url, self._why())
        c = self.config
        lines = [("The AI (F1 closes)", "heading"),
                 (f"  Mode: {MODE_NAMES[c.ai_mode]}", "default"),
                 (f"  Backend: {dict(BACKENDS)[c.ai_backend]}", "default")]
        models = chosen(c)
        lines += [(f"  {name}: {label(c.ai_backend, models[role])}", "default") for role, name in ROLES]
        if c.ai_backend == "opencode":
            lines.append(("  Only OpenCode's free models are offered." +
                          (" (Reading them from OpenCode...)" if self.opencode.known() is None else ""), "dim"))
        why = self._why()
        if why:
            lines.append((f"  Cannot be used: {why}.", "red"))
        lines += [("", "default"), ("Pick a line to change it.", "dim")]
        return lines

    def pick(self, n: int) -> str | None:
        """What picking choice n did: 'mode', 'backend', 'model', 'close', or None."""
        if self.page == "connect":
            self.page = "main"
            return None
        c = self.config
        if n == 1:
            return "mode"  # the App cycles it, by the mode's own rules (6a)
        if n == 2:
            names = [b for b, _ in BACKENDS]
            c.ai_backend = names[(names.index(c.ai_backend) + 1) % len(names)]
            return "backend"
        if n in (3, 4):
            role = ROLES[n - 3][0]
            options = self.models(c.ai_backend)
            current = chosen(c)[role]
            following = options[(options.index(current) + 1) % len(options)] if current in options else options[0]
            c.ai_models = {**(c.ai_models or {}), c.ai_backend: {**chosen(c), role: following}}
            return "model"
        if n == 5:
            self.page = "connect"
            return None
        if n == 6:
            return "close"
        return None
