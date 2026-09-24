"""Lineage in the engine (phase 4b): aging as time passes, death, and the death screen."""

import systems.bonds as bonds
import systems.mortality as mortality
import systems.succession as succession
from engine.actions import Action, Choice
from systems.halls import settle_town
from world.gen.materialize import populate
from systems.time import format_date
from world.events import commit

DEATH_VERBS = frozenset({"succeed", "newcomer", "new_world", "look", "help", "unknown", "ambiguous"})


class LineageMixin:
    exit_to: str | None = None  # "title" or "newcomer": the App takes over (phase 4b spec 5.3)

    def _dying(self) -> dict | None:
        return self.player.data.get("dying")

    def _death_choices(self) -> list:
        choices = []
        for person, kind in bonds.candidates(self.world, self.player.id)[:8]:
            p = self.world.entity(person)
            where = self.world.entity(self.world.targets(person, "located_in")[0]).name \
                if self.world.targets(person, "located_in") else "the roads"
            label = f"{p.name} - {bonds.relation_word(self.world, person, kind)}, {int(p.data.get('age', 30))}, " \
                    f"{p.data.get('realm', 'mortal')}, in {where}"
            choices.append(Choice(label, Action("succeed", person)))
        return choices + [Choice("A newcomer in this world", Action("newcomer")), Choice("A new world", Action("new_world"))]

    def _death_lines(self) -> list:
        self.focus, self.submenu, self.combat, self.encounter, self.challenger = None, None, None, None, None
        return [(mortality.epitaph(self.world, self.player.id), "heading"),
                ("Your story is not over. Choose how it goes on.", "system")]

    def _restore(self) -> None:
        if self._dying():
            return  # a fight or an encounter means nothing to the dead; nothing to rebuild
        super()._restore()

    def _special_choices(self):
        if self._dying():
            return self._death_choices()[:9], []
        return super()._special_choices()

    def _special_status(self):
        if self._dying():
            return f"{self.player.name} | dead | {format_date(self.world.time)}"
        return super()._special_status()

    def _special_art(self):
        if self._dying():
            grave = self.world.targets(self.player.id, "buried_at")
            town = self.world.entity(grave[0]) if grave else None
            if town is not None and town.kind == "town":
                return {"type": "scene", "terrain": town.data["terrain"], "settlement": town.data["kind"],
                        "watch": 3, "hall": None}
        return super()._special_art()

    def _gate(self, action: Action):
        if self._dying() and action.verb not in DEATH_VERBS:
            return self._turn([("You are dead. Choose how your story goes on.", "system")])
        return super()._gate(action)

    def _status_suffix(self) -> str:
        suffix = super()._status_suffix()
        age = self.player.data.get("age")
        if age is None or self._dying():
            return suffix
        near = ", lifespan near" if mortality.lifespan_near(self.world, self.player.id) else ""
        return f" ({int(age)}{near}){suffix}"

    def _before_scene(self) -> None:
        super()._before_scene()
        mortality.player_lived_to(self.world, self.player.id)  # the player's life clock starts with the first scene

    def _after_commit(self, ids: list, events: list) -> list:
        lines = super()._after_commit(ids, events)
        me = self.player.id
        if self._dying() or self.player.data.get("dead"):
            return lines
        for event_id, event in zip(ids, events):
            if event.kind == "deviation" and event.actors and event.actors[0] == me:
                deaths = mortality.deviation_death_events(self.world, me, event_id)
                if deaths:
                    return lines + self._commit(deaths) + self._death_lines()
        named = self.player.data.get("named_heir")
        if named is not None and named not in [p for p, _ in bonds.candidates(self.world, me)]:
            self.world.update_data(me, named_heir=None)  # a named heir who can no longer inherit is forgotten
        aged = mortality.age_events(self.world, me)
        if aged:
            commit(self.world, aged[:1])  # quiet: aging is not an event worth a line of prose
            if aged[0].data["white_hair"]:
                lines.append(("Your hair has gone white.", "dim"))
            if len(aged) > 1:
                lines += self._commit(aged[1:]) + self._death_lines()
        return lines

    def _after_duel(self, data: dict) -> list:
        cause = data.get("player_killed")
        if not cause:
            return super()._after_duel(data)
        deaths = mortality.death_events(self.world, self.player.id, cause, data.get("killer"), record=False)
        return self._commit(deaths) + self._death_lines()  # nothing else follows a death

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        world, me = self.world, self.player.id
        if npc.data.get("beast") or npc.data.get("dead"):
            return extras
        if bonds.propose_block(world, me, npc.id) is None:
            extras.append(Choice("Propose marriage", Action("propose", npc.id)))
        if bonds.disciple_block(world, me, npc.id) is None and (npc.id, "disciple") not in bonds.kin_of(world, me):
            extras.append(Choice("Take them as your disciple", Action("take_disciple", npc.id)))
        if bonds.sworn_block(world, me, npc.id) is None:
            oath = "sisterhood" if npc.data.get("gender") == "woman" else "brotherhood"
            extras.append(Choice(f"Swear {oath}", Action("swear", npc.id)))
        heirs = [p for p, _ in bonds.candidates(world, me)]
        if npc.id in heirs and self.player.data.get("named_heir") != npc.id:
            extras.append(Choice("Name them your heir", Action("name_heir", npc.id)))
        return extras

    def _bond(self, npc, block, build):
        if self.focus != npc:
            return self._turn([("Speak with them first.", "system")])
        if block is not None and (why := block(self.world, self.player.id, npc)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(build(self.world, self.player.id, npc, self.place.id)))

    def _do_propose(self, npc):
        return self._bond(npc, bonds.propose_block, bonds.propose_events)

    def _do_take_disciple(self, npc):
        return self._bond(npc, bonds.disciple_block, bonds.disciple_events)

    def _do_swear(self, npc):
        return self._bond(npc, bonds.sworn_block, bonds.sworn_events)

    def _do_name_heir(self, npc):
        if npc not in [p for p, _ in bonds.candidates(self.world, self.player.id)]:
            return self._turn([("They cannot be your heir.", "system")])
        return self._bond(npc, None, bonds.name_heir_events)

    def _do_succeed(self, heir):
        if not self._dying():
            return self._turn([("You are not dead.", "system")])
        events = succession.succession_events(self.world, self.player.id, heir) if isinstance(heir, int) else []
        if not events:
            return self._turn([("They cannot carry on for you.", "system")])
        lines = self._commit(events)  # the player is now the heir
        populate(self.world, self.place.id)
        settle_town(self.world, self.place.id)
        self._last_look = None
        self._before_scene()
        return self._turn(lines + self._describe("arrive") + self._presence() + self._after_arrival())

    def _do_newcomer(self, _target):
        if not self._dying():
            return self._turn([("You are not dead.", "system")])
        self.exit_to = "newcomer"
        return self._turn([("Someone new walks into this world.", "system")])

    def _do_lineage(self, _target):
        from engine.lineage_page import lineage_lines
        return self._turn(lineage_lines(self.world, self.player.id))

    def _do_new_world(self, _target):
        if not self._dying():
            return self._turn([("You are not dead.", "system")])
        self.exit_to = "title"
        return self._turn([("A new world awaits.", "system")])
