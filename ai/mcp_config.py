"""The MCP config `claude -p` is given (phase 6 spec 2): one server, DeepMurim's, over the current save."""

import json
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent / "mcp_server" / "server.py"


def config(save: Path) -> dict:
    return {"mcpServers": {"deepmurim": {"command": sys.executable, "args": [str(SERVER), str(Path(save).resolve())]}}}


def write_config(save: Path, folder: Path) -> Path:
    """Write the config beside the session's other files; the bridge passes its path to every tooled call."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "deepmurim-mcp.json"
    target.write_text(json.dumps(config(save), indent=2), encoding="utf-8")
    return target
