"""The DeepMurim MCP server (phase 6 spec 5): `python mcp_server/server.py <save>` serves the read-only tools over
stdio to one `claude -p` call. The viewer is the save's player, fixed at start: no tool asks as anyone else."""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # run as a script by `claude -p`

from mcp.server.mcpserver import MCPServer  # noqa: E402

from mcp_server import tools as T  # noqa: E402
from world.db import World  # noqa: E402

INSTRUCTIONS = ("Read-only views of a DeepMurim world, as the player knows it. Name people as the player knows "
                "them. Nothing here changes the world.")


def build(save) -> MCPServer:
    view = T.View(World.open_readonly(save))
    server = MCPServer("deepmurim", instructions=INSTRUCTIONS)

    def sheet() -> str:
        return T.sheet(view)

    def known_people() -> str:
        return T.known_people(view)

    def person(name: str) -> str:
        return T.person(view, name)

    def memories_of(name: str) -> str:
        return T.memories_of(view, name)

    def beliefs_of(name: str, topic: str = "") -> str:
        return T.beliefs_of(view, name, topic)

    def rumours(topic: str = "") -> str:
        return T.rumours(view, topic)

    def chronicle(query: str = "", limit: int = 10) -> str:
        return T.chronicle(view, query, limit)

    def factions() -> str:
        return T.factions(view)

    def place() -> str:
        return T.place(view)

    for fn, tool in zip((sheet, known_people, person, memories_of, beliefs_of, rumours, chronicle, factions, place),
                        T.TOOLS):
        server.add_tool(fn, name=tool.__name__, description=tool.__doc__)
    return server


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: server.py <save.world>", file=sys.stderr)
        return 2
    build(argv[1]).run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
