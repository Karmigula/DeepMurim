"""Karma in the engine (phase 5f spec 7): the temple, a fortune teller's reading, and heaven's doings told as they
come (a sinner's misfortune, heaven taking notice, a smith's estate paying back)."""

import systems.karma as K
import systems.karma_world as KW
from engine.actions import Action, Choice
from narrate.brief import event_brief
from systems.purse import silver_of
from world.events import Event

ALMS = (10, 50, 200)
FORTUNE_PRICE = 50
FORTUNE_TELLER = "fortune teller"
REACTIONS = frozenset({"misfortune", "commission_refunded", "tribulation_gathers"})  # the clock's and listeners'


class KarmaMixin:
    def _general_extras(self) -> list:
        extras = super()._general_extras()
        if KW.has_temple(self.world, self.place.id):
            extras.append(Choice("Visit the temple", Action("temple")))
        return extras

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        if npc.data.get("occupation") == FORTUNE_TELLER:
            extras.append(Choice(f"Have your fortune read ({FORTUNE_PRICE} silver)", Action("fortune", npc.id)))
        return extras

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        if self.focus is None and self.submenu == "temple":
            options["temple"] = ([Choice(f"Give {n} silver in alms", Action("alms", n)) for n in ALMS]
                                 + [Choice("Burn incense", Action("incense"))], Action("back"))
        return options

    def _do_temple(self, _target):
        if not KW.has_temple(self.world, self.place.id):
            return self._turn([("There is no temple here.", "system")])
        self.submenu = "temple"
        return self._turn([("Incense smoke drifts under the eaves. A monk sweeps the steps.", "dim")])

    def _do_alms(self, silver):
        world, me, here = self.world, self.player.id, self.place.id
        silver = silver if isinstance(silver, int) else ALMS[1]
        self.submenu = "temple"
        if (why := KW.alms_block(world, me, here, silver)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(KW.alms_events(world, me, here, silver)))

    def _do_incense(self, _target):
        self.submenu = "temple"
        if not KW.has_temple(self.world, self.place.id):
            return self._turn([("There is no temple here.", "system")])
        return self._turn(self._commit(KW.incense_events(self.world, self.player.id, self.place.id)))

    def _do_fortune(self, npc):
        world, me, here = self.world, self.player.id, self.place.id
        npc = npc if npc is not None else self.focus
        teller = world.entity(npc) if isinstance(npc, int) else None
        if teller is None or teller.data.get("occupation") != FORTUNE_TELLER or self.focus != npc:
            return self._turn([("There is no fortune teller before you.", "system")])
        if silver_of(world, me) < FORTUNE_PRICE:
            return self._turn([(f"A reading costs {FORTUNE_PRICE} silver.", "system")])
        return self._turn(self._commit([Event("fortune_read", (me, npc), here, {"silver": FORTUNE_PRICE,
                                                                                "balance": K.balance(world, me)})]))

    def _after_commit(self, ids: list, events: list) -> list:
        """Heaven's doings in the clock and in listeners, told as they come."""
        lines = super()._after_commit(ids, events)
        if not ids:
            return lines
        me, done = self.player.id, set(ids)
        for entry in reversed(self.world.chronicle_about(me, limit=12)):
            if entry.id > min(ids) and entry.id not in done and entry.kind in REACTIONS and entry.actors[0] == me \
                    and entry.data.get("why") != "breakthrough":  # a breakthrough's is the engine's own, told already
                lines += self.narrator.narrate(event_brief(self.world, entry.id, entry))
                if entry.kind == "tribulation_gathers":
                    lines += self._wave_lines()
        return lines
