"""The MCP tools (phase 6 spec 5): plain functions over a read-only world, each answering as the viewer knows.

Every answer is plain text with no entity ids. People are named as the viewer knows them; a name the viewer does
not know (or that fits two people) is an answer of its own, never a lookup of the truth. A belief comes with an
opaque handle (for 6b's `tell`), a hash of the seed, the holder and the fact, never an id.
"""

import hashlib
import sqlite3

from engine.game import Game
from engine.journal import summarize
from engine.sheet import sheet_lines
from engine.standing_page import standing_lines
from narrate.gossip_text import rumour_text
from systems.attitude import attitude
from systems.beliefs import known_people as heard_of
from world.gen.materialize import people_at

QUIET = frozenset({"exchange", "player_aged", "delve_moved", "delve_rested"})
MAX_PEOPLE, MAX_LINES = 40, 20
UNKNOWN = "No one you know by that name."


class View:
    """The world as one viewer may read it."""

    def __init__(self, world) -> None:
        self.world = world
        self.game = Game(world)
        self.viewer = world.get_meta("player_id")

    def known(self) -> list[int]:
        here = [p.id for p in people_at(self.world, self.game.place.id, exclude=self.viewer)]
        return list(dict.fromkeys(here + heard_of(self.world, self.viewer)))

    def find(self, name: str) -> int | None:
        wanted = name.strip().lower()
        hits = [p for p in self.known() if self.world.entity(p).name.lower() == wanted]
        return hits[0] if len(hits) == 1 else None

    def handle(self, holder: int, fact_id: int) -> str:
        raw = f"{self.world.world_seed}:{holder}:{fact_id}".encode()
        return "b" + hashlib.sha256(raw).hexdigest()[:10]


def _safe(fn):
    """A read the read-only world refuses (it would have written) is told as not known, never a crash."""
    def run(*args):
        try:
            return fn(*args)
        except sqlite3.OperationalError:
            return "That is not known."
    run.__name__, run.__doc__ = fn.__name__, fn.__doc__
    return run


@_safe
def sheet(view: View) -> str:
    """Your own sheet: realm, body, arts, standing (as the sheet page shows it)."""
    return "\n".join(text for text, _ in sheet_lines(view.world, view.viewer) if text.strip())


@_safe
def known_people(view: View) -> str:
    """Everyone you have met or heard of: name, role, whether they are here, how they feel toward you."""
    world, here = view.world, {p.id for p in people_at(view.world, view.game.place.id)}
    lines = []
    for pid in view.known()[:MAX_PEOPLE]:
        person = world.entity(pid)
        where = "here" if pid in here else "elsewhere"
        feeling = attitude(world, pid, view.viewer).word if person.kind == "person" else "unknown"
        lines.append(f"{person.name}, {person.data.get('occupation', 'stranger')}, {where}, {feeling}")
    return "\n".join(lines) or "You know no one yet."


@_safe
def person(view: View, name: str) -> str:
    """One person as you know them: role, traits, realm, and what is said of them."""
    pid = view.find(name)
    if pid is None:
        return UNKNOWN
    world, entity = view.world, view.world.entity(pid)
    d = entity.data
    lines = [f"{entity.name}: {d.get('occupation', 'stranger')}; {', '.join(d.get('traits', ())) or 'unremarkable'}; "
             f"{d.get('realm', 'mortal')}; toward you: {attitude(world, pid, view.viewer).word}"]
    said = [rumour_text(world, b.variant, view.viewer)
            for b, _ in world.known_facts_about([view.viewer], actors=[pid])][-MAX_LINES:]
    return "\n".join(lines + [f"said of them: {s}" for s in said])


@_safe
def memories_of(view: View, name: str) -> str:
    """What that person remembers of you, and how they feel about it."""
    pid = view.find(name)
    if pid is None:
        return UNKNOWN
    world = view.world
    found = world.memories(pid, about=view.viewer)[-MAX_LINES:]
    return "\n".join(f"{m.feeling}: {summarize(world, m.event)}" for m in found) or "They remember nothing of you."


@_safe
def beliefs_of(view: View, name: str, topic: str = "") -> str:
    """What that person holds to be so on a topic (empty: anything), each with a handle to tell it by."""
    pid = view.find(name)
    if pid is None:
        return UNKNOWN
    world, wanted = view.world, topic.strip().lower()
    out = []
    for belief, fact in world.known_facts(pid):
        text = rumour_text(world, belief.variant, view.viewer)
        if not wanted or wanted in text.lower():
            out.append(f"[{view.handle(pid, fact.id)}] {text}")
    return "\n".join(out[-MAX_LINES:]) or "They hold nothing on that."


@_safe
def rumours(view: View, topic: str = "") -> str:
    """What you have heard on a topic (empty: the latest)."""
    world, wanted = view.world, topic.strip().lower()
    texts = [rumour_text(world, b.variant, view.viewer) for b, _ in world.known_facts(view.viewer)]
    return "\n".join([t for t in texts if not wanted or wanted in t.lower()][-MAX_LINES:]) or "You have heard nothing."


@_safe
def chronicle(view: View, query: str = "", limit: int = 10) -> str:
    """Your own past, as your journal tells it, newest last (query: words to look for)."""
    world, wanted = view.world, query.strip().lower()
    entries = [e for e in reversed(world.chronicle_about(view.viewer, limit=300)) if e.kind not in QUIET]
    lines = [summarize(world, e) for e in entries]
    lines = [line for line in lines if not wanted or wanted in line.lower()]
    return "\n".join(lines[-max(1, min(int(limit), MAX_LINES)):]) or "Nothing of the kind."


@_safe
def factions(view: View) -> str:
    """Your standing with the factions you know, and your ranks."""
    return "\n".join(t for t, _ in standing_lines(view.world, view.viewer, view.game.place.id) if t.strip())


@_safe
def place(view: View) -> str:
    """Where you are: the place, who is here, what is here."""
    head = f"{view.game.place.name}"
    return "\n".join([head] + [t for t, _ in view.game._presence()])


TOOLS = (sheet, known_people, person, memories_of, beliefs_of, rumours, chronicle, factions, place)
