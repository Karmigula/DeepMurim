"""Creating an art from fragments, in the engine."""

import systems.inventing as inventing
from engine.actions import Action, Choice


class InventingMixin:
    def _practise_extras(self, body) -> list:
        extras = super()._practise_extras(body)
        if inventing.why_not_create(self.world, self.player.id) is None:
            extras.append(Choice("Create a new art...", Action("create_menu")))
        return extras

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        if self.focus is None:
            forms = inventing.creatable_forms(self.world, self.player.id)
            options["create_menu"] = (
                [Choice(f"Create a {form} art (a week of seclusion)", Action("create_art", form)) for form in forms],
                Action("practise_menu"),
            )
        return options

    def _do_create_menu(self, _target):
        if busy := self._busy():
            return busy
        reason = inventing.why_not_create(self.world, self.player.id)
        if reason:
            return self._turn([(reason, "system")])
        self.submenu = "create_menu"
        return self._turn([("What form will your art take?", "system")])

    def _do_create_art(self, form):
        if busy := self._busy():
            return busy
        events = inventing.create_events(self.world, self.player.id, self.place.id, form)
        return self._cultivated(events, "You cannot create that art now.")
