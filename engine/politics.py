"""Politics in the engine (phase 3b spec 6): summons, judgement, and exposing the rival."""

import random

import systems.politics as politics
from engine.actions import Action, Choice
from systems import factions as F
from world.seed import rng_for

JUDGE_VERBS = frozenset({"judgement", "help", "journal", "unknown", "ambiguous", "standing"})
JUDGE_LABELS = (("accept", "Accept the punishment"), ("combat", "Demand trial by combat"),
                ("deny", "Deny the charge"), ("refuse", "Refuse to answer"))


class PoliticsMixin:
    def _summons(self):
        return self.player.data.get("summons") if self.combat is None and self.encounter is None else None

    def _gate(self, action):
        if self._summons() and action.verb not in JUDGE_VERBS:
            name = self.world.entity(self._summons()["faction"]).name
            return self._turn([(f"The {name} is waiting for your answer.", "system")])
        return super()._gate(action)

    def _special_choices(self):
        if self._summons():
            return [Choice(label, Action("judgement", key)) for key, label in JUDGE_LABELS], []
        return super()._special_choices()

    def _summon_check(self) -> list:
        if self.combat is not None or self.encounter is not None or self.challenger is not None:
            return []
        events = politics.summons_events(self.world, self.player.id, self.place.id)
        return self._commit(events) if events else []

    def _after_look(self) -> list:
        return super()._after_look() + self._summon_check()

    def _after_arrival(self) -> list:
        return super()._after_arrival() + self._summon_check()

    def _do_judgement(self, choice):
        summons = self._summons()
        if not summons:
            return self._turn([("No one has summoned you.", "system")])
        me, place = self.player.id, self.place.id
        if choice == "accept":
            return self._turn(self._commit(politics.judged_events(self.world, me, place, "punished")))
        if choice == "refuse":
            return self._turn(self._commit(politics.judged_events(self.world, me, place, "expelled")))
        if choice == "combat":
            return self._turn(self._start_duel(summons["accuser"], "duel", purpose={"judgement": summons["fact"]}))
        if choice == "deny":
            roll = rng_for(self.world.world_seed, f"deny:{summons['fact']}:{me}").random()
            outcome = "cleared" if roll < politics.deny_chance(self.world, me, summons, place) else "expelled"
            return self._turn(self._commit(politics.judged_events(self.world, me, place, outcome)))
        return self._turn([("Accept, fight, deny or refuse?", "system")])

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        fact = (data.get("purpose") or {}).get("judgement")
        summons = self.player.data.get("summons")
        if fact and summons and summons["fact"] == fact:
            outcome = "cleared" if data["result"] == "won" else "punished"
            lines += self._commit(politics.judged_events(self.world, self.player.id, self.place.id, outcome))
        return lines

    def _faction_options(self, npc) -> list:
        options = super()._faction_options(npc)
        ex = self.player.data.get("exposable")
        if ex and F.membership(self.world, self.player.id, ex["faction"])[1].get("sponsor") == npc.id:
            options.insert(0, Choice(f"Expose {self.world.entity(ex['rival']).name}", Action("expose", ex["faction"])))
        return options

    def _do_expose(self, faction_id):
        ex = self.player.data.get("exposable")
        if not ex or ex["faction"] != faction_id or self.focus is None:
            return self._turn([("You have nothing to expose.", "system")])
        self.submenu = None
        return self._turn(self._commit(politics.exposed_events(self.world, self.player.id, self.place.id)))
