"""Joining factions in the engine (phase 3b spec 4)."""

from engine.actions import Action, Choice
from systems import halls, membership
from systems.purse import payment_events, silver_of


class JoiningMixin:
    def _faction_options(self, npc) -> list:
        options = super()._faction_options(npc)
        me, town = self.player.id, self.place.id
        trial = self.player.data.get("trial")
        for fid in halls.recruits_for(self.world, npc.id):
            name = self.world.entity(fid).name
            if trial and trial["faction"] == fid:
                if trial["kind"] == "chief":
                    options.append(Choice("Challenge the chief", Action("chief_duel", fid)))
                    options.append(Choice(f"Pay tribute ({membership.TRIBUTE} silver)", Action("tribute", fid)))
                continue
            found = membership.F.membership(self.world, me, fid)
            if found or self.world.entity(fid).data["type"] == "alliance":
                continue
            options.append(Choice(f"Ask to join the {name}", Action("join", fid)))
            if membership.secret_possible(self.world, me, fid, town):
                options.append(Choice(f"Ask to join the {name} in secret", Action("join_secret", fid)))
        return options

    def _do_join(self, faction_id, secret: bool = False):
        npc = self.focus
        if npc is None or faction_id not in halls.recruits_for(self.world, npc):
            return self._turn([("They cannot take you in.", "system")])
        me, town = self.player.id, self.place.id
        if secret:
            if not membership.secret_possible(self.world, me, faction_id, town):
                return self._turn([("They would see through you.", "system")])
        elif (why := membership.refusal(self.world, me, faction_id, town)) is not None:
            return self._turn([(why, "system")])
        kind = membership.TRIALS[self.world.entity(faction_id).data["type"]]
        if kind == "escort" and silver_of(self.world, me) < membership.FEE:
            return self._turn([(f"The guild's fee is {membership.FEE} silver.", "system")])
        self.submenu = None
        if kind is None:
            return self._turn(self._commit(membership.joined_events(self.world, me, npc, faction_id, town, secret)))
        lines = self._commit(membership.trial_events(self.world, me, npc, faction_id, town, secret))
        if kind == "spar":
            opponent = next(iter(halls.staff_at(self.world, faction_id, town, roles=("disciple",))), npc)
            return self._turn(lines + self._start_duel(opponent, "test", purpose={"join": faction_id}))
        return self._turn(lines)

    def _do_chief_duel(self, faction_id):
        trial = self.player.data.get("trial")
        if self.focus is None or not trial or trial["faction"] != faction_id or trial["kind"] != "chief":
            return self._turn([("There is no chief to challenge.", "system")])
        chief = next(iter(halls.staff_at(self.world, faction_id, self.place.id, roles=("leader",))), self.focus)
        self.submenu = None
        return self._turn(self._start_duel(chief, "duel", purpose={"join": faction_id}))

    def _do_join_secret(self, faction_id):
        return self._do_join(faction_id, secret=True)

    def _do_tribute(self, faction_id):
        trial = self.player.data.get("trial")
        if self.focus is None or not trial or trial["faction"] != faction_id or trial["kind"] != "chief":
            return self._turn([("There is no tribute to pay.", "system")])
        if silver_of(self.world, self.player.id) < membership.TRIBUTE:
            return self._turn([(f"You don't have {membership.TRIBUTE} silver.", "system")])
        events = payment_events(self.player.id, self.focus, self.place.id, membership.TRIBUTE, "tribute")
        events += membership.joined_events(self.world, self.player.id, trial["recruiter"], faction_id, self.place.id,
                                           trial["secret"])
        self.submenu = None
        return self._turn(self._commit(events))

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        faction = (data.get("purpose") or {}).get("join")
        trial = self.player.data.get("trial")
        if faction and trial and trial["faction"] == faction:
            me, place = self.player.id, self.place.id
            if data["result"] in ("passed", "won"):
                events = membership.joined_events(self.world, me, trial["recruiter"], faction, place, trial["secret"])
            else:
                events = membership.trial_failed_events(me, place, faction)
            lines += self._commit(events)
        return lines

    def _trial_progress(self) -> list:
        state = membership.trial_done(self.world, self.player.id)
        if state is None:
            return []
        trial = self.player.data["trial"]
        me, place = self.player.id, self.place.id
        if state:
            return self._commit(membership.joined_events(self.world, me, trial["recruiter"], trial["faction"], place,
                                                         trial["secret"]))
        return self._commit(membership.trial_failed_events(me, place, trial["faction"]))

    def _after_commit(self, ids: list, events: list) -> list:
        lines = super()._after_commit(ids, events)
        if any(e.kind in ("joined", "trial_failed", "trial_begun") for e in events):
            return lines
        return lines + self._trial_progress()

    def _after_look(self) -> list:
        return super()._after_look() + self._trial_progress()

    def _after_arrival(self) -> list:
        return super()._after_arrival() + self._trial_progress()
