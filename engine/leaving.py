"""Leaving factions in the engine (phase 3b spec 7)."""

import systems.duties as duties
import systems.leaving as leaving
from engine.actions import Action, Choice
from systems import factions as F
from systems import halls
from systems.membership import left_events
from systems.purse import silver_of


class LeavingMixin:
    def _faction_options(self, npc) -> list:
        options = super()._faction_options(npc)
        me = self.player.id
        for fid in halls.recruits_for(self.world, npc.id):
            found = F.membership(self.world, me, fid)
            if not found or found[1].get("status", "member") != "member":
                continue
            if self.world.entity(fid).data["type"] not in leaving.NEVER_RELEASE:
                price = leaving.release_price(self.world, me, fid)
                options.append(Choice(f"Ask for release ({price} silver)", Action("release", fid)))
                if duties.open_duty(self.world, me) is None:
                    options.append(Choice("Ask for release by a final duty", Action("release_duty", fid)))
            options.append(Choice(f"Desert the {self.world.entity(fid).name}", Action("desert", fid)))
        return options

    def _member_here(self, faction_id) -> bool:
        found = F.membership(self.world, self.player.id, faction_id)
        return bool(found and found[1].get("status", "member") == "member" and self.focus is not None
                    and faction_id in halls.recruits_for(self.world, self.focus))

    def _do_release(self, faction_id):
        if not self._member_here(faction_id) or self.world.entity(faction_id).data["type"] in leaving.NEVER_RELEASE:
            return self._turn([("They will not release you.", "system")])
        price = leaving.release_price(self.world, self.player.id, faction_id)
        if silver_of(self.world, self.player.id) < price:
            return self._turn([(f"Release costs {price} silver.", "system")])
        self.submenu = None
        return self._turn(self._commit(leaving.release_events(self.world, self.player.id, faction_id, self.focus, self.place.id)))

    def _do_release_duty(self, faction_id):
        if not self._member_here(faction_id) or self.world.entity(faction_id).data["type"] in leaving.NEVER_RELEASE:
            return self._turn([("They will not release you.", "system")])
        if duties.open_duty(self.world, self.player.id) is not None:
            return self._turn([("Finish your current duty first.", "system")])
        self.submenu = None
        return self._turn(self._commit(duties.issue_events(self.world, self.player.id, faction_id, self.focus,
                                                           self.place.id, release=True)))

    def _do_desert(self, faction_id):
        found = F.membership(self.world, self.player.id, faction_id)
        if not found or found[1].get("status", "member") != "member":
            return self._turn([("You are not one of them.", "system")])
        self.submenu, self.focus = None, None
        return self._turn(self._commit(left_events(self.world, self.player.id, faction_id, self.place.id, "deserter")))

    def _after_commit(self, ids: list, events: list) -> list:
        lines = super()._after_commit(ids, events)
        for event in events:
            if event.kind == "duty_done" and event.data.get("release"):
                lines += self._commit(left_events(self.world, self.player.id, event.data["faction"], self.place.id, "released"))
        return lines

    def _spy_check(self) -> list:
        events = leaving.spy_checks(self.world, self.player.id, self.place.id)
        return self._commit(events) if events else []

    def _after_look(self) -> list:
        return super()._after_look() + self._spy_check()

    def _after_arrival(self) -> list:
        return super()._after_arrival() + self._spy_check()
