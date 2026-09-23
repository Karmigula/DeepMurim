"""The law in the engine (phase 3b spec 8): arrest as a gated moment, like a challenge."""

import systems.encounters as encounters
import systems.law as law
from engine.actions import Action, Choice

LAW_VERBS = frozenset({"arrest", "help", "journal", "unknown", "ambiguous", "standing"})


class LawMixin:
    def _arrest(self):
        return self.player.data.get("arrest") if self.combat is None and self.encounter is None else None

    def _gate(self, action):
        if self._arrest() and action.verb not in LAW_VERBS:
            return self._turn([("A constable has you by the arm. Answer the charge first.", "system")])
        return super()._gate(action)

    def _special_choices(self):
        a = self._arrest()
        if a:
            return [Choice(f"Pay the fine ({a['bounty']} silver)", Action("arrest", "pay")),
                    Choice(f"Serve time ({max(1, a['bounty'] // 5)} days)", Action("arrest", "jail")),
                    Choice("Fight your way free", Action("arrest", "fight")),
                    Choice("Try to flee", Action("arrest", "flee"))], []
        return super()._special_choices()

    def _law_check(self) -> list:
        if self.combat is not None or self.encounter is not None or self.challenger is not None:
            return []
        events = law.arrest_events(self.world, self.player.id, self.place.id)
        return self._commit(events) if events else []

    def _after_look(self) -> list:
        return super()._after_look() + self._law_check()

    def _after_arrival(self) -> list:
        return super()._after_arrival() + self._law_check()

    def _do_arrest(self, choice):
        a = self._arrest()
        if not a:
            return self._turn([("No one is arresting you.", "system")])
        me, place = self.player.id, self.place.id
        if choice == "pay":
            if law.silver_of(self.world, me) < a["bounty"]:
                return self._turn([(f"You don't have {a['bounty']} silver.", "system")])
            return self._turn(self._commit(law.fine_events(self.world, me, place)))
        if choice == "jail":
            return self._turn(self._commit(law.jail_events(self.world, me, place)))
        if choice == "flee" and encounters.flee_succeeds(self.world, me, a["constable"]):
            return self._turn(self._commit(law.escape_events(self.world, me, place)))
        if choice in ("fight", "flee"):
            lines = self._commit(law.escape_events(self.world, me, place))
            return self._turn(lines + self._start_duel(a["constable"], "duel", purpose={"arrest": True}))
        return self._turn([("Pay, serve, fight or flee?", "system")])
