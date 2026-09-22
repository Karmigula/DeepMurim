"""The engine: Actions in, Turns out. The only code that commits events."""

import random
from dataclasses import dataclass

import systems.talk as talk
import systems.travel as travel
from engine.journal import summarize
from narrate.base import Line, Narrator
from narrate.brief import event_brief, scene_brief
from narrate.procedural import ProceduralNarrator
from systems.time import format_date
from world.db import Entity, SaveError, World
from world.events import Event, commit
from world.gen.materialize import ensure_town, people_at, populate, region_of

HELP = [
    ("Type a number, or a command:", "system"),
    ("  look | talk <name> | go <place or direction> | ask <work|town> | bye | journal | help", "system"),
    ("  F2 swap art side | F3 hide art | PgUp/PgDn scroll | F11 fullscreen | Esc menu", "system"),
]


@dataclass(frozen=True)
class Action:
    verb: str
    target: object = None


@dataclass(frozen=True)
class Choice:
    label: str
    action: Action


@dataclass
class Turn:
    lines: list[Line]
    choices: list[Choice]
    art: dict
    status: str


class Game:
    def __init__(self, world: World, narrator: Narrator | None = None) -> None:
        self.world = world
        self.narrator = narrator or ProceduralNarrator()
        self.focus: int | None = None
        self._pending: list[Line] = []

    @classmethod
    def new(cls, path, player_name: str, world_seed: int | None = None, narrator=None) -> "Game":
        seed = world_seed if world_seed is not None else random.SystemRandom().randrange(2**31)
        world = World.create(path, seed)
        town = ensure_town(world, 0, 0, 0)
        with world.transaction():
            player = world.add_entity("person", player_name, {"is_player": True, "age": 18, "realm": "mortal"})
            world.relate(player, town, "located_in")
            world.set_meta("player_id", player)
        populate(world, town)
        game = cls(world, narrator)
        game._pending = game._commit([Event("began", (player,), town)])
        return game

    @classmethod
    def load(cls, path, narrator=None) -> "Game":
        world = World.open(path)
        if world.get_meta("player_id") is None:
            world.close()
            raise SaveError(f"{world.path.name} has no player")
        return cls(world, narrator)

    def close(self) -> None:
        self.world.close()

    @property
    def player(self) -> Entity:
        return self.world.entity(self.world.get_meta("player_id"))

    @property
    def place(self) -> Entity:
        return travel.location_of(self.world, self.player.id)

    # --- turns ----------------------------------------------------------------
    def start(self) -> Turn:
        return self.look()

    def look(self) -> Turn:
        return self._do_look(None)

    def perform(self, action: Action) -> Turn:
        handler = getattr(self, f"_do_{action.verb}", None)
        if handler is None:
            return self._turn([(f"You can't do that ({action.verb}).", "system")])
        return handler(action.target)

    def _do_look(self, _target) -> Turn:
        self.focus = None
        return self._turn(self._describe("look") + self._presence())

    def _do_travel(self, dest) -> Turn:
        routes = {r.dest: r for r in travel.routes_from(self.world, self.place)}
        route = routes.get(tuple(dest) if dest is not None else None)
        if route is None:
            return self._turn([("You can't get there from here.", "system")])
        self.focus = None
        lines = self._commit(travel.travel_events(self.player.id, self.place.id, route))
        populate(self.world, self.place.id)
        return self._turn(lines + self._describe("arrive") + self._presence())

    def _do_talk(self, npc_id) -> Turn:
        present = {p.id for p in people_at(self.world, self.place.id, exclude=self.player.id)}
        if npc_id not in present:
            return self._turn([("There is no one like that here.", "system")])
        self.focus = npc_id
        return self._turn(self._commit(talk.greet_events(self.world, self.player.id, npc_id, self.place.id)))

    def _do_ask(self, topic) -> Turn:
        if self.focus is None or topic not in talk.TOPICS:
            return self._turn([("Ask whom, about what?", "system")])
        return self._turn(self._commit(talk.ask_events(self.player.id, self.focus, self.place.id, topic)))

    def _do_farewell(self, _target) -> Turn:
        if self.focus is None:
            return self._turn([("You aren't talking to anyone.", "system")])
        lines = self._commit(talk.farewell_events(self.player.id, self.focus, self.place.id))
        self.focus = None
        return self._turn(lines)

    def _do_journal(self, _target) -> Turn:
        entries = list(reversed(self.world.chronicle_about(self.player.id, limit=15)))
        lines = [(f"Chronicle of {self.player.name}:", "gold")]
        lines += [(summarize(self.world, e), "dim") for e in entries]
        return self._turn(lines)

    def _do_help(self, _target) -> Turn:
        return self._turn(list(HELP))

    def _do_unknown(self, text) -> Turn:
        return self._turn([(f"Not understood: {str(text)[:60]!r}. Type 'help' for commands.", "system")])

    def _do_ambiguous(self, options) -> Turn:
        turn = self._turn([("Which one do you mean?", "system")])
        turn.choices = list(options)
        return turn

    # --- helpers --------------------------------------------------------------
    def _commit(self, events: list[Event]) -> list[Line]:
        ids = commit(self.world, events)
        lines: list[Line] = []
        for event_id, event in zip(ids, events):
            lines += self.narrator.narrate(event_brief(self.world, event_id, event))
        return lines

    def _describe(self, salt: str) -> list[Line]:
        return self.narrator.narrate(scene_brief(self.world, self.place.id, self.player.id, salt))

    def _presence(self) -> list[Line]:
        people = people_at(self.world, self.place.id, exclude=self.player.id)
        if not people:
            return [("No one of note is here.", "dim")]
        described = []
        for person in people:
            known = " (knows you)" if talk.conversations_with(self.world, person.id, self.player.id) else ""
            described.append(f"{person.name} the {person.data.get('occupation', 'stranger')}{known}")
        return [("Here: " + ", ".join(described) + ".", "dim")]

    def _choices(self) -> list[Choice]:
        if self.focus is not None:
            return [
                Choice("Ask about their work", Action("ask", "work")),
                Choice(f"Ask about {self.place.name}", Action("ask", "town")),
                Choice("Say farewell", Action("farewell")),
            ]
        choices = [
            Choice(f"Talk to {p.name} ({p.data.get('occupation', 'stranger')})", Action("talk", p.id))
            for p in people_at(self.world, self.place.id, exclude=self.player.id)
        ]
        choices += [Choice(r.label, Action("travel", r.dest)) for r in travel.routes_from(self.world, self.place)]
        choices += [Choice("Look around", Action("look")), Choice("Read your journal", Action("journal"))]
        return choices

    def _art(self) -> dict:
        if self.focus is not None:
            return {"type": "portrait", "parts": self.world.entity(self.focus).data["portrait"]}
        place = self.place
        return {"type": "scene", "terrain": place.data["terrain"], "settlement": place.data["kind"], "watch": self.world.time % 4}

    def _status(self) -> str:
        player, place = self.player, self.place
        region = region_of(self.world, place.id)
        return f"{player.name} | {player.data.get('realm', 'mortal')} | {format_date(self.world.time)} | {place.name}, {region.name}"

    def _turn(self, lines: list[Line]) -> Turn:
        lines, self._pending = self._pending + lines, []
        return Turn(lines, self._choices(), self._art(), self._status())
