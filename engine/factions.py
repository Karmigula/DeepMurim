"""Factions in the engine (phase 3b spec 9): halls in towns, and the Faction matters... submenu."""

from engine.actions import Action, Choice
from narrate.outcomes import cap
from systems import halls
from systems.beliefs import apparent_to
from systems.standing import standing


class FactionsMixin:
    def _restore(self) -> None:
        super()._restore()
        halls.settle_town(self.world, self.place.id)

    def _presence_tag(self, person) -> str:
        tag = halls.faction_tag(self.world, person.id, self.place.id)
        return f" ({tag})" if tag else super()._presence_tag(person)

    def _presence_extras(self) -> list:
        lines = super()._presence_extras()
        town = self.world.entity(self.place.id)
        for fid in halls.halls_here(self.world, self.place.id):
            name = self.world.entity(fid).name
            where = "its seat" if fid in town.data.get("seats", []) else "a hall"
            lines.append((f"The {name} keeps {where} here.", "dim"))
        return lines

    def _scene_extras(self) -> dict:
        extras = super()._scene_extras()
        town = self.world.entity(self.place.id)
        if town.data.get("seats"):
            extras["hall"] = "gate"
        elif town.data.get("halls"):
            extras["hall"] = "hall"
        return extras

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        if self._faction_options(npc):
            extras.insert(0, Choice("Faction matters...", Action("faction_menu")))
        return extras

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        if self.focus is not None and self.submenu == "faction":
            options["faction"] = (self._faction_options(self.world.entity(self.focus)), Action("talk_menu"))
        return options

    def _faction_options(self, npc) -> list:
        options = super()._faction_options(npc)
        for fid in halls.recruits_for(self.world, npc.id):
            name = self.world.entity(fid).name
            options.append(Choice(f"Ask how the {name} regards you", Action("faction_view", fid)))
        return options

    def _do_faction_view(self, faction_id):
        if self.focus is None or faction_id not in halls.recruits_for(self.world, self.focus):
            return self._turn([("They cannot speak for that faction.", "system")])
        view = standing(self.world, faction_id, apparent_to(self.world, self.focus, self.player.id))
        why = f" ({'; '.join(view.reasons)})" if view.reasons else ""
        speaker = cap(self.world.entity(self.focus).name)
        name = self.world.entity(faction_id).name
        return self._turn([(f"{speaker} tells you that the {name} holds you {view.word}{why}.", "dim")])

    def _do_faction_menu(self, _target):
        if self.focus is None:
            return self._turn([("There is no one to discuss that with.", "system")])
        if not self._faction_options(self.world.entity(self.focus)):
            return self._turn([("They have no faction business with you.", "system")])
        self.submenu = "faction"
        return self._turn([("What is your business?", "system")])
