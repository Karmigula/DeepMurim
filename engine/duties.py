"""Duties in the engine (phase 3b spec 5)."""

import systems.duties as duties
from engine.actions import Action, Choice
from systems import factions as F
from systems import halls
from world.events import Event


class DutiesMixin:
    def _faction_options(self, npc) -> list:
        options = super()._faction_options(npc)
        me, town = self.player.id, self.place.id
        duty = duties.open_duty(self.world, me)
        for fid in halls.recruits_for(self.world, npc.id):
            found = F.membership(self.world, me, fid)
            if not found or found[1].get("status", "member") != "member" or halls.keeper_at(self.world, fid, town) != npc.id:
                continue
            if duty is None:
                options.append(Choice("Ask for a duty", Action("duty", fid)))
            elif duty.data["faction"] == fid:
                options.append(Choice("Abandon your duty", Action("abandon_duty", fid)))
        return options

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        duty = duties.open_duty(self.world, self.player.id)
        if duty is not None and duty.data["kind"] == "collect" and duty.data["target"] == npc.id and not duty.data.get("paid"):
            extras.insert(0, Choice("Demand the debt", Action("demand", duty.id)))
        return extras

    def _do_duty(self, faction_id):
        found = F.membership(self.world, self.player.id, faction_id)
        if self.focus is None or not found or halls.keeper_at(self.world, faction_id, self.place.id) != self.focus:
            return self._turn([("Only the hall keeper assigns duties.", "system")])
        if duties.open_duty(self.world, self.player.id) is not None:
            return self._turn([("Finish your current duty first.", "system")])
        self.submenu = None
        return self._turn(self._commit(duties.issue_events(self.world, self.player.id, faction_id, self.focus, self.place.id)))

    def _do_abandon_duty(self, faction_id):
        duty = duties.open_duty(self.world, self.player.id)
        if duty is None or duty.data["faction"] != faction_id:
            return self._turn([("You have no duty to abandon.", "system")])
        self.submenu = None
        return self._turn(self._commit(duties.failed_events(self.world, self.player.id, self.place.id, "abandoned")))

    def _do_demand(self, duty_id):
        duty = duties.open_duty(self.world, self.player.id)
        if duty is None or duty.id != duty_id or self.focus != duty.data["target"]:
            return self._turn([("They owe your faction nothing.", "system")])
        debtor = self.focus
        if duties.pays_willingly(self.world, debtor, self.player.id):
            return self._turn(self._commit(duties.debt_events(self.player.id, debtor, self.place.id, duty.id, duty.data["amount"])))
        return self._turn(self._start_duel(debtor, "duel", purpose={"collect": duty.id}))

    def _duty_progress(self) -> list:
        state = duties.progress(self.world, self.player.id)
        if state == "done":
            return self._commit(duties.done_events(self.world, self.player.id, self.place.id))
        if state == "failed":
            return self._commit(duties.failed_events(self.world, self.player.id, self.place.id))
        return []

    def _after_commit(self, ids: list, events: list) -> list:
        lines = super()._after_commit(ids, events)
        if any(e.kind in ("duty_issued", "duty_done", "duty_failed") for e in events):
            return lines
        raid = None
        for event_id, event in zip(ids, events):
            duties.guarded_events(self.world, self.player.id, event)
            if raid is None and self.combat is None and duties.raid_due(self.world, self.player.id, event_id, event):
                raid = duties.open_duty(self.world, self.player.id)
        lines += self._duty_progress()
        if raid is not None and duties.open_duty(self.world, self.player.id) is not None:
            enemy = duties.raider(self.world, raid, self.place.id)
            lines += self._commit([Event("raid", (self.player.id, enemy), self.place.id, {"duty": raid.id})])
            lines += self._start_duel(enemy, "duel", purpose={"raid": raid.id})
        return lines

    def _after_look(self) -> list:
        return super()._after_look() + self._duty_progress()

    def _after_arrival(self) -> list:
        return super()._after_arrival() + self._duty_progress()

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        purpose = data.get("purpose") or {}
        duty = duties.open_duty(self.world, self.player.id)
        if duty is None:
            return lines
        if purpose.get("collect") == duty.id and data["result"] == "won":
            lines += self._commit(duties.debt_events(self.player.id, duty.data["target"], self.place.id, duty.id,
                                                     duty.data["amount"]))
        elif purpose.get("raid") == duty.id and data["result"] in ("lost", "fled"):
            lines += self._commit(duties.failed_events(self.world, self.player.id, self.place.id, "raided"))
        return lines
