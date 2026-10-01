"""Which models each backend may use (phase 6 spec 13.2): Claude Code's three, and OpenCode's free ones only."""

import json
import subprocess

CLAUDE_MODELS = (("claude-haiku-4-5", "Haiku 4.5"), ("claude-sonnet-5", "Sonnet 5"), ("claude-opus-5-5", "Opus 5.5"))
CLAUDE_DEFAULTS = {"narrate": "claude-haiku-4-5", "talk": "claude-sonnet-5"}
OPENCODE_DEFAULT = "opencode/big-pickle"


def parse_verbose(text: str) -> dict[str, dict]:
    """`opencode models --verbose`: each model's name on a line, then its JSON. {name: its metadata}."""
    models, name, block = {}, None, []
    for line in text.splitlines():
        if block or line.startswith("{"):
            block.append(line)
            if line.startswith("}"):
                try:
                    models[name] = json.loads("\n".join(block))
                except (ValueError, TypeError):
                    pass
                block = []
        elif line.strip() and not line.startswith(" "):
            name = line.strip()
    return {k: v for k, v in models.items() if k}


def free(models: dict[str, dict]) -> list[str]:
    """OpenCode's own free models: of its `opencode` provider, costing nothing, not retired. A price of 0 alone is
    not enough: a preset, a router, or a coding plan billed elsewhere reports 0 too."""
    out = []
    for name, meta in models.items():
        cost = meta.get("cost") or {}
        own = meta.get("providerID", name.split("/", 1)[0]) == "opencode"
        if own and cost.get("input") == 0 and cost.get("output") == 0 and meta.get("status", "active") != "deprecated":
            out.append(name)
    return sorted(out)


class OpenCodeModels:
    """OpenCode's free models, asked of OpenCode once a session."""

    def __init__(self, exe: str | None, runner=subprocess.run) -> None:
        self.exe, self.runner = exe, runner
        self._found: list[str] | None = None

    def free(self) -> list[str]:
        if self._found is None:
            self._found = []
            if self.exe:
                try:
                    done = self.runner([self.exe, "models", "--verbose"], capture_output=True, text=True,
                                       encoding="utf-8", timeout=60)
                    self._found = free(parse_verbose(done.stdout or ""))
                except (OSError, subprocess.SubprocessError):
                    self._found = []
        return list(self._found)


def label(backend: str, model: str) -> str:
    if backend == "claude_code":
        return dict(CLAUDE_MODELS).get(model, model)
    return model.split("/", 1)[-1]
