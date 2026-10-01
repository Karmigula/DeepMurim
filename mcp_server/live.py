"""The long-lived DeepMurim MCP server (phase 6 spec 13.4): one, over streamable HTTP on localhost, while the AI is on.

Both backends connect to it (and the player's own Claude Code or OpenCode sessions may: the Connect page says how).
It runs in a thread of the game itself, reading the save read-only and anew on every request.
"""

import logging
import socket
import threading
import time
from pathlib import Path

STARTUP = 10.0
for _noisy in ("mcp", "httpx", "httpx2", "uvicorn", "uvicorn.error", "uvicorn.access"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)  # every request would be told on the console


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class LiveServer:
    def __init__(self, save: Path) -> None:
        self.save = Path(save)
        self.url: str | None = None
        self._server = None
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> str:
        """Start it (once) and return its address: http://127.0.0.1:<port>/mcp."""
        if self.running:
            return self.url
        import uvicorn
        from mcp_server.server import build
        port = free_port()
        app = build(self.save, fresh=True).streamable_http_app(host="127.0.0.1")
        self._server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning",
                                                     lifespan="on"))
        self._thread = threading.Thread(target=self._server.run, name="deepmurim-mcp", daemon=True)
        self._thread.start()
        deadline = time.monotonic() + STARTUP
        while not self._server.started:
            if time.monotonic() > deadline or not self._thread.is_alive():
                self.stop()
                raise RuntimeError("the MCP server did not start")
            time.sleep(0.05)
        self.url = f"http://127.0.0.1:{port}/mcp"
        return self.url

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(5)
        self._server, self._thread, self.url = None, None, None
