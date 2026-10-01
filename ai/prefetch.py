"""The lookups a model would likely ask for, done before it is asked (phase 6 spec 13.5).

A tool round trip costs the model seconds; the lookup itself costs the engine milliseconds. So for a typed action
or a line of talk (6c), the people here, what the ones in play remember of the player, and what anyone here holds
that touches the words typed go into the prompt; the tools remain for anything else.
"""

import re

from mcp_server import tools as T
from world.gen.materialize import people_at

MAX_BELIEFS = 6
WORD = re.compile(r"[a-z']{4,}")
COMMON = frozenset({"that", "this", "with", "what", "about", "your", "have", "from", "they", "them", "there", "their",
                    "would", "could", "should", "into", "where", "when", "which", "some", "will", "just", "tell"})


def words_of(text: str) -> set[str]:
    return {w for w in WORD.findall(text.lower()) if w not in COMMON}


def build_prefetch(game, typed: str, focus: int | None = None) -> str:
    """What the engine already knows the model will want: a text block for the prompt, ids never shown."""
    view = T.View(game.world)
    here = people_at(game.world, game.place.id, exclude=game.player.id)
    wanted = words_of(typed)
    said = typed.lower()
    named = [p for p in here if p.id == focus or re.search(rf"\b{re.escape(p.name.lower())}\b", said)]
    lines = ["PEOPLE HERE:"] + [f"- {p.name}, {p.data.get('occupation', 'stranger')}" for p in here[:15]]
    for person in named[:3]:
        lines += [f"{person.name.upper()} AS YOU KNOW THEM:", "- " + T.person(view, person.name).replace("\n", "\n- "),
                  f"WHAT {person.name.upper()} REMEMBERS OF YOU:",
                  "- " + T.memories_of(view, person.name).replace("\n", "\n- ")]
    held = []
    for person in (named or here)[:6]:
        for line in T.beliefs_of(view, person.name, "").splitlines():
            if line.startswith("[") and wanted & words_of(line):
                held.append(f"- {person.name} holds: {line}")
    if held:
        lines += ["WHAT THOSE HERE HOLD ON YOUR WORDS (the [handle] tells it):"] + held[:MAX_BELIEFS]
    return "\n".join(lines)
