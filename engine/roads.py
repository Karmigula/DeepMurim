"""Road encounters and grudge challenges in the engine (phase 2 spec §10)."""

import systems.encounters as encounters
from engine.actions import Action, Choice
from narrate.outcomes import cap
from systems.purse import payment_events, silver_of

ROAD_VERBS = frozenset({"road", "help", "journal", "unknown", "ambiguous"})
CHALLENGE_VERBS = frozenset({"answer_challenge", "help", "journal", "unknown", "ambiguous"})


class RoadsMixin:
    def _restore(self) -> None:
        super()._restore()
        if self.combat is None:
            self.encounter = encounters.pending_encounter(self.world, self.player.id)
            self.challenger = encounters.pending_challenge(self.world, self.player.id)

    def _gate(self, action):
        if self.encounter is not None and action.verb not in ROAD_VERBS:
            name = cap(self.world.entity(self.encounter["person"]).name)
            return self._turn([(f"{name} blocks the road. Deal with them first.", "system")])
        if self.challenger is not None and action.verb not in CHALLENGE_VERBS:
            name = self.world.entity(self.challenger).name
            return self._turn([(f"{name} is waiting for your answer.", "system")])
        return super()._gate(action)

    def _special_choices(self):
        if self.encounter is not None:
            return self._road_choices(), []
        if self.challenger is not None:
            return [Choice("Accept the challenge", Action("answer_challenge", True)),
                    Choice("Decline", Action("answer_challenge", False))], []
        return super()._special_choices()

    def _road_choices(self) -> list[Choice]:
        e = self.encounter
        choices = [Choice("Fight", Action("road", "fight")), Choice("Try to flee", Action("road", "flee"))]
        if e["kind"] == "bandit":
            choices.append(Choice(f"Pay the toll ({e['toll']} silver)", Action("road", "pay")))
        if e["kind"] != "beast":
            choices.append(Choice("Talk your way past", Action("road", "talk")))
        return choices

    def _special_art(self):
        who = self.encounter["person"] if self.encounter else self.challenger
        if who is None:
            return super()._special_art()
        person = self.world.entity(who)
        return {"type": "duel", "parts": person.data.get("portrait"), "beast": bool(person.data.get("beast")),
                "harm": 0.0, "condition": "fresh"}

    def _after_arrival(self) -> list:
        lines = super()._after_arrival()
        events = encounters.road_encounter_events(self.world, self.player.id, self.place)
        if events:
            lines += self._commit(events)
            if events[-1].kind == "encounter":
                self.encounter = encounters.encounter_state(events[-1])
        if self.encounter is None:
            lines += self._grudges()
        return lines

    def _after_look(self) -> list:
        return super()._after_look() + self._grudges()

    def _grudges(self) -> list:
        """Someone here with a grudge, a dead kinsman or a rival's pride may call you out."""
        npc = encounters.challenge_from(self.world, self.player.id, self.place.id)
        if npc is None:
            return []
        lines = self._commit(encounters.challenge_events(self.player.id, npc, self.place.id))
        self.challenger = npc
        return lines

    def _resolve(self, how: str) -> list:
        e = self.encounter
        self.encounter = None
        return self._commit(encounters.resolved_events(self.player.id, e["person"], self.place.id, how, e["kind"]))

    def _do_road(self, how):
        if self.encounter is None:
            return self._turn([("Nothing stands in your way.", "system")])
        e, me, place = self.encounter, self.player.id, self.place.id
        person = e["person"]
        if how == "pay":
            if e["kind"] != "bandit":
                return self._turn([("There is no toll to pay.", "system")])
            if silver_of(self.world, me) < e["toll"]:
                return self._turn([(f"You don't have {e['toll']} silver.", "system")])
            lines = self._commit(payment_events(me, person, place, e["toll"], "toll"))
            return self._turn(lines + self._resolve("paid"))
        if how == "talk":
            if e["kind"] == "beast":
                return self._turn([("It does not understand words.", "system")])
            if encounters.talk_succeeds(self.world, person, me, e["kind"]):
                return self._turn(self._resolve("talked"))
            return self._turn(self._resolve("fight") + self._start_duel(person, "encounter"))
        if how == "flee":
            if encounters.flee_succeeds(self.world, me, person):
                return self._turn(self._resolve("fled"))
            return self._turn(self._resolve("fight") + self._start_duel(person, "encounter", opening="opponent"))
        if how == "fight":
            return self._turn(self._resolve("fight") + self._start_duel(person, "encounter"))
        return self._turn([("Fight, flee, pay or talk?", "system")])

    def _do_answer_challenge(self, accept):
        if self.challenger is None:
            return self._turn([("No one has challenged you.", "system")])
        npc, self.challenger = self.challenger, None
        if accept:
            return self._turn(self._start_duel(npc, "duel"))
        return self._turn(self._commit(encounters.decline_events(self.player.id, npc, self.place.id)))
