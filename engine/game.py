"""The engine: Actions in, Turns out. The only code that commits events.

Feature mixins (fights, roads, dealings, invention) extend the engine through
the hooks in engine.hooks, so this file keeps the core loop: looking, talking,
travelling, cultivating, and turning state into a Turn.
"""

import random
import sqlite3

import systems.cultivation as cultivation
import systems.talk as talk
import systems.travel as travel
from engine.actions import Action, Choice, Turn
from engine.dealings import DealingsMixin
from engine.fight import FightMixin
from engine.gossip import GossipMixin
from engine.masks import MasksMixin
from engine.roads import RoadsMixin
from engine.hooks import GameHooks
from engine.inventing import InventingMixin
from engine.journal import summarize
from narrate.base import Line, Narrator
from narrate.brief import event_brief, scene_brief
from narrate.procedural import ProceduralNarrator
from systems.attitude import attitude
from systems.beliefs import apparent_to
from systems.bodies import load_body
from systems.factions import ensure_roster
from systems.creation import CreationChoice, apply_creation, build, wanderer_arts
from systems.realms import MAX_REALM, REALMS, energy_words, realm_title, requirement
from systems.techniques import known_arts, martial_arts, usable
from systems.time import format_date
from world.body import EXTRAORDINARY, Body, unhealed
from world.db import Entity, SaveError, World
from world.events import Event, commit
from world.gen.materialize import ensure_town, people_at, populate, region_of

__all__ = ["Action", "Choice", "Game", "Turn"]

MAX_SHOWN = 9  # digits 1-9 pick a choice with one key
KEEP_SUBMENU = frozenset({
    "people", "routes", "cultivate", "practise_menu", "meridian_menu", "ambiguous",
    "use_menu", "learn_menu", "browse", "create_menu",
})
QUIET_KINDS = frozenset({"exchange"})
PATIENCE_SHIFT = {"warm": 1, "hostile": -1, "hateful": -1}  # phase 3a spec 3.2  # too many to list in the journal
BUSY = "Finish your conversation first."

HELP = [
    ("Type a number, or a command:", "system"),
    ("  look | talk <name> | go <place or direction> | ask <work|town> | bye | journal | help", "system"),
    ("  cultivate | meditate <day|week|month|season> | practise <art> | open <meridian> | rest | breakthrough", "system"),
    ("  challenge | spar | strike | feint | guard | probe | flee | yield | spare | rob | cripple | kill", "system"),
    ("  news | ask about <name> | tell | rumours | wear mask | remove mask", "system"),
    ("  F2 swap art side | F3 hide art | F4 character sheet | F9 report a bug | F12 debug | Esc menu", "system"),
]


class Game(GossipMixin, MasksMixin, InventingMixin, DealingsMixin, RoadsMixin, FightMixin, GameHooks):
    def __init__(self, world: World, narrator: Narrator | None = None) -> None:
        self.world = world
        self.narrator = narrator or ProceduralNarrator()
        self.focus: int | None = None
        self.submenu: str | None = None
        self.last_briefs: list = []  # what the narrator was given this turn (debug overlay, invariants)
        self.combat = None       # a systems.duel.Duel while fighting
        self.encounter = None    # a road encounter waiting for an answer (Task 7)
        self.challenger = None   # someone who just challenged the player (Task 7)
        self._last_ids: list[int] = []
        self._last_look: tuple[int, int] | None = None
        self._pending: list[Line] = []

    @classmethod
    def new(cls, path, player_name: str, world_seed: int | None = None, narrator=None,
            creation: CreationChoice | None = None) -> "Game":
        seed = world_seed if world_seed is not None else random.SystemRandom().randrange(2**31)
        world = World.create(path, seed)
        town = ensure_town(world, 0, 0, 0)
        made = build(seed, creation or CreationChoice())
        with world.transaction():
            player = world.add_entity("person", player_name, {"is_player": True, "age": 18, "realm": "mortal"})
            world.relate(player, town, "located_in")
            world.set_meta("player_id", player)
            arts = apply_creation(world, player, made)
        populate(world, town)
        ensure_roster(world)
        game = cls(world, narrator)
        game._pending = game._commit([Event("began", (player,), town, {"origin": made.origin.title, "arts": arts})])
        return game

    @classmethod
    def load(cls, path, narrator=None) -> "Game":
        world = World.open(path)
        try:
            player_id = world.get_meta("player_id")
            player = world.entity(player_id) if isinstance(player_id, int) else None
            if player is None:
                raise SaveError(f"{world.path.name} has no player")
            if not world.targets(player.id, "located_in"):
                raise SaveError(f"{world.path.name}: {player.name} is nowhere in the world")
        except SaveError:
            world.close()
            raise
        except (sqlite3.DatabaseError, ValueError, KeyError, TypeError) as exc:
            world.close()
            raise SaveError(f"{world.path.name} is damaged ({exc})") from exc
        game = cls(world, narrator)
        ensure_roster(world)  # a save from before factions (phase 3b)
        if "body" not in player.data:  # a save from before bodies existed
            place = travel.location_of(world, player.id).id
            data = {"origin": "Wanderer", "arts": wanderer_arts(world.world_seed)}
            game._pending = game._commit([Event("body_awakened", (player.id,), place, data)])
        game._restore()
        return game

    def close(self) -> None:
        self.world.close()

    @property
    def player(self) -> Entity:
        return self.world.entity(self.world.get_meta("player_id"))

    @property
    def place(self) -> Entity:
        return travel.location_of(self.world, self.player.id)

    def body(self) -> Body:
        return load_body(self.world, self.player.id)

    # --- turns ----------------------------------------------------------------
    def start(self) -> Turn:
        return self.look()

    def look(self) -> Turn:
        self.last_briefs = []
        if self.combat is not None or self.encounter is not None or self.challenger is not None:
            return self._turn([])  # resuming mid-fight or mid-encounter: show its menu, not the town
        return self._do_look(None)

    def perform(self, action: Action) -> Turn:
        self.last_briefs = []
        gate = self._gate(action)
        if gate is not None:
            return gate
        handler = getattr(self, f"_do_{action.verb}", None)
        if handler is None:
            return self._turn([(f"You can't do that ({action.verb}).", "system")])
        if action.verb not in KEEP_SUBMENU:
            self.submenu = None
        return handler(action.target)

    def _do_people(self, _target) -> Turn:
        self.submenu = "people"
        return self._turn([("Who do you approach?", "system")])

    def _do_routes(self, _target) -> Turn:
        self.submenu = "routes"
        return self._turn([("Where to?", "system")])

    def _do_back(self, _target) -> Turn:
        return self._turn([])

    def _do_talk_menu(self, _target) -> Turn:
        return self._turn([])  # back to the plain conversation menu; focus is kept

    def _do_look(self, _target) -> Turn:
        self.focus = None
        here = (self.place.id, self.world.time)
        if here == self._last_look:
            return self._turn([("Nothing has changed since you last looked.", "dim")] + self._presence() + self._after_look())
        self._last_look = here
        return self._turn(self._describe("look") + self._presence() + self._after_look())

    def _do_travel(self, dest) -> Turn:
        routes = {r.dest: r for r in travel.routes_from(self.world, self.place)}
        route = routes.get(tuple(dest) if dest is not None else None)
        if route is None:
            return self._turn([("You can't get there from here.", "system")])
        self.focus = None
        lines = self._commit(travel.travel_events(self.player.id, self.place.id, route))
        populate(self.world, self.place.id)
        self._last_look = (self.place.id, self.world.time)
        return self._turn(lines + self._describe("arrive") + self._presence() + self._after_arrival())

    def _do_talk(self, npc_id) -> Turn:
        present = {p.id for p in people_at(self.world, self.place.id, exclude=self.player.id)}
        if npc_id not in present:
            return self._turn([("There is no one like that here.", "system")])
        self.focus = npc_id
        return self._turn(self._commit(talk.greet_events(self.world, self.player.id, npc_id, self.place.id)))

    def _do_ask(self, topic) -> Turn:
        if self.focus is None or topic not in talk.TOPICS:
            return self._turn([("Ask whom, about what?", "system")])
        npc, me = self.world.entity(self.focus), self.player.id
        if (lost := self._lost_patience(npc, topic)) is not None:
            return lost
        return self._turn(self._commit(talk.ask_events(me, npc.id, self.place.id, topic)))

    def _patience(self, npc) -> int:
        feeling = attitude(self.world, npc.id, apparent_to(self.world, npc.id, self.player.id)).word
        return max(1, talk.patience_of(npc) + PATIENCE_SHIFT.get(feeling, 0))

    def _lost_patience(self, npc, topic: str):
        """A Turn if this question is one too many for them, else None."""
        me = self.player.id
        if talk.repeats_if_asked(self.world, npc.id, me, topic) <= self._patience(npc):
            return None
        lines = self._commit(talk.lost_patience_events(me, npc.id, self.place.id, topic))
        self.focus = None
        return self._turn(lines)

    def _do_farewell(self, _target) -> Turn:
        if self.focus is None:
            return self._turn([("You aren't talking to anyone.", "system")])
        lines = self._commit(talk.farewell_events(self.player.id, self.focus, self.place.id))
        self.focus = None
        return self._turn(lines)

    def _do_journal(self, _target) -> Turn:
        entries = [e for e in reversed(self.world.chronicle_about(self.player.id, limit=60)) if e.kind not in QUIET_KINDS]
        lines = [(f"Chronicle of {self.player.name}:", "heading")]
        lines += [(summarize(self.world, e), "dim") for e in entries[-15:]]
        return self._turn(lines)

    def _do_help(self, _target) -> Turn:
        return self._turn(list(HELP))

    def _do_unknown(self, text) -> Turn:
        return self._turn([(f"Not understood: {str(text)[:60]!r}. Type 'help' for commands.", "system")])

    def _do_ambiguous(self, options) -> Turn:
        turn = self._turn([("Which one do you mean?", "system")])
        turn.choices = list(options)
        return turn

    # --- cultivation ----------------------------------------------------------------
    def _busy(self) -> Turn | None:
        return self._turn([(BUSY, "system")]) if self.focus is not None else None

    def _cultivated(self, events: list[Event], reason: str) -> Turn:
        if not events:
            return self._turn([(reason, "system")])
        lines = self._commit(events)
        self.submenu = "cultivate"
        return self._turn(lines)

    def _do_cultivate(self, _target) -> Turn:
        if busy := self._busy():
            return busy
        self.submenu = "cultivate"
        return self._turn(self._cultivation_status())

    def _do_practise_menu(self, _target) -> Turn:
        if busy := self._busy():
            return busy
        self.submenu = "practise_menu"
        return self._turn([("Which art will you drill?", "system")])

    def _do_meridian_menu(self, _target) -> Turn:
        if busy := self._busy():
            return busy
        self.submenu = "meridian_menu"
        return self._turn([("Which sealed meridian will you work on?", "system")])

    def _do_meditate(self, days) -> Turn:
        if busy := self._busy():
            return busy
        days = days if days in cultivation.MEDITATE_OPTIONS.values() else 7
        events = cultivation.meditate_events(self.world, self.player.id, self.place.id, days)
        return self._cultivated(events, "You cannot meditate now.")

    def _do_practise(self, technique_id) -> Turn:
        if busy := self._busy():
            return busy
        art = next((a for a in martial_arts(self.world, self.player.id) if a.technique.id == technique_id), None)
        if art is None:
            return self._turn([("You don't know that art.", "system")])
        if not usable(self.body(), art.technique.data):
            return self._turn([(f"A severed meridian puts the {art.name} beyond you now.", "system")])
        events = cultivation.practise_events(self.world, self.player.id, self.place.id, technique_id)
        return self._cultivated(events, "You cannot practise that now.")

    def _do_open_meridian(self, name) -> Turn:
        if busy := self._busy():
            return busy
        reason = cultivation.why_not_open(self.body(), name)
        if reason:
            return self._turn([(reason, "system")])
        events = cultivation.open_meridian_events(self.world, self.player.id, self.place.id, name)
        return self._cultivated(events, "Nothing happens.")

    def _do_rest(self, days) -> Turn:
        if busy := self._busy():
            return busy
        days = days if isinstance(days, int) and 0 < days <= 90 else cultivation.REST_DAYS
        events = cultivation.rest_events(self.world, self.player.id, self.place.id, days)
        return self._cultivated(events, "You cannot rest now.")

    def _do_breakthrough(self, _target) -> Turn:
        if busy := self._busy():
            return busy
        events = cultivation.breakthrough_events(self.world, self.player.id, self.place.id)
        return self._cultivated(events, "Your qi has not yet reached a bottleneck.")

    def _cultivation_status(self) -> list[Line]:
        body = self.body()
        who = "a mortal" if body.realm == 0 else f"a {realm_title(body)} warrior"
        lines = [(f"You are {who}, with {energy_words(body.energy_years)}.", "dim")]
        if body.bottleneck and body.realm < MAX_REALM:
            lines.append((f"Your qi presses against a bottleneck. Only a breakthrough to {REALMS[body.realm + 1].name} will let it grow.", "dim"))
            ready, needed = requirement(body, known_arts(self.world, self.player.id))
            if not ready:
                lines.append((f"You are not ready to break through: {needed}", "dim"))
        if body.deviation > 60:
            lines.append(("Your qi feels unruly; a deviation may be near.", "dim"))
        hurt = sorted({i.location for i in unhealed(body, self.world.time)})
        if hurt:
            lines.append(("Still healing: " + ", ".join(hurt) + ".", "dim"))
        return lines

    # --- helpers --------------------------------------------------------------
    def _commit(self, events: list[Event]) -> list[Line]:
        events = self._stamp(list(events))
        ids = commit(self.world, events)
        self._last_ids = ids
        lines: list[Line] = []
        for event_id, event in zip(ids, events):
            brief = event_brief(self.world, event_id, event)
            self.last_briefs.append(brief)
            lines += self.narrator.narrate(brief)
        lines += self._after_commit(ids, events)
        self._last_ids = ids  # reactions commit too; callers want their own events' ids
        return lines

    def _describe(self, salt: str) -> list[Line]:
        brief = scene_brief(self.world, self.place.id, self.player.id, salt)
        self.last_briefs.append(brief)
        return self.narrator.narrate(brief)

    def _presence(self) -> list[Line]:
        people = people_at(self.world, self.place.id, exclude=self.player.id)
        if not people:
            return [("No one of note is here.", "dim")]
        described = []
        for person in people:
            known = " (knows you)" if talk.conversations_with(self.world, person.id, self.player.id) else ""
            described.append(f"{person.name} the {person.data.get('occupation', 'stranger')}{known}")
        return [("Here: " + ", ".join(described) + ".", "dim")]

    # --- menus ----------------------------------------------------------------------
    def _choices(self) -> tuple[list[Choice], list[Choice]]:
        """(shown, extra). At most MAX_SHOWN are shown, so each has a single-key number.
        Everything valid but not shown goes in `extra`, so typed commands still reach it."""
        special = self._special_choices()
        if special is not None:
            return special
        feature_menus = self._submenu_options()
        if self.focus is not None:
            if self.submenu in feature_menus:
                options, back = feature_menus[self.submenu]
                return options[: MAX_SHOWN - 1] + [Choice("Back", back)], []
            npc = self.world.entity(self.focus)
            options = [
                Choice("Ask about their work", Action("ask", "work")),
                Choice(f"Ask about {self.place.name}", Action("ask", "town")),
                *self._conversation_extras(npc),
            ]
            shown = options[: MAX_SHOWN - 1] + [Choice("Say farewell", Action("farewell"))]
            return shown, options[MAX_SHOWN - 1:] + self._conversation_hidden(npc)
        body = self.body()
        people = [
            Choice(f"Talk to {p.name} ({p.data.get('occupation', 'stranger')})", Action("talk", p.id))
            for p in people_at(self.world, self.place.id, exclude=self.player.id)
        ]
        routes = [Choice(r.label, Action("travel", r.dest)) for r in travel.routes_from(self.world, self.place)]
        general = [Choice("Look around", Action("look")), Choice("Read your journal", Action("journal"))]
        general += self._general_extras()
        practise = [Choice(f"Practise the {a.name} for a week", Action("practise", a.technique.id))
                    for a in martial_arts(self.world, self.player.id)] + self._practise_extras(body)
        cultivate = self._cultivation_choices(body, bool(practise))
        meridians = [Choice(f"Work on the {m} meridian for a week", Action("open_meridian", m))
                     for m in EXTRAORDINARY if body.meridians[m].state == "blocked"]
        submenus = {
            "people": (people, Action("back")), "routes": (routes, Action("back")),
            "cultivate": (cultivate, Action("back")),
            "practise_menu": (practise, Action("cultivate")), "meridian_menu": (meridians, Action("cultivate")),
        }
        submenus.update(feature_menus)
        everything = people + routes + cultivate + practise + meridians + general
        for options, _ in feature_menus.values():
            everything += [c for c in options if c not in everything]
        if self.submenu in submenus:
            options, back = submenus[self.submenu]
            shown = options[: MAX_SHOWN - 1] + [Choice("Back", back)]
        else:
            shown = self._main_menu(people, routes, general)
        return shown, [c for c in everything if c not in shown]

    def _main_menu(self, people: list[Choice], routes: list[Choice], general: list[Choice]) -> list[Choice]:
        entry = Choice("Cultivate...", Action("cultivate"))
        fold = {"people": False, "routes": False}

        def menu() -> list[Choice]:
            items = [Choice(f"Talk to someone here ({len(people)})", Action("people"))] if fold["people"] else list(people)
            items += [Choice(f"Travel ({len(routes)} routes)", Action("routes"))] if fold["routes"] else list(routes)
            return items + [entry] + general

        for name, group in (("people", people), ("routes", routes)):
            if len(menu()) > MAX_SHOWN and len(group) > 1:
                fold[name] = True
        return menu()

    def _cultivation_choices(self, body: Body, can_practise: bool) -> list[Choice]:
        options = [
            Choice("Meditate for a day", Action("meditate", 1)),
            Choice("Meditate for a week", Action("meditate", 7)),
            Choice("Meditate for a month", Action("meditate", 30)),
            Choice("Seclusion for a season (90 days)", Action("meditate", 90)),
        ]
        if can_practise:
            options.append(Choice("Practise an art...", Action("practise_menu")))
        if any(body.meridians[m].state == "blocked" for m in EXTRAORDINARY):
            options.append(Choice("Work on opening a meridian...", Action("meridian_menu")))
        options.append(Choice("Rest for a week", Action("rest", 7)))
        if body.bottleneck and body.realm < MAX_REALM:
            options.append(Choice(f"Attempt breakthrough to {REALMS[body.realm + 1].name}", Action("breakthrough")))
        return options

    def _art(self) -> dict:
        special = self._special_art()
        if special is not None:
            return special
        if self.focus is not None:
            return {"type": "portrait", "parts": self.world.entity(self.focus).data["portrait"]}
        place = self.place
        return {"type": "scene", "terrain": place.data["terrain"], "settlement": place.data["kind"], "watch": self.world.time % 4}

    def _status(self) -> str:
        special = self._special_status()
        if special is not None:
            return special
        player, place = self.player, self.place
        region = region_of(self.world, place.id)
        return f"{player.name}{self._status_suffix()} | {realm_title(self.body())} | {format_date(self.world.time)} | {place.name}, {region.name}"

    def _turn(self, lines: list[Line]) -> Turn:
        lines, self._pending = self._pending + lines, []
        shown, extra = self._choices()
        return Turn(lines, shown, self._art(), self._status(), extra)
