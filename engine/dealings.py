"""Learning from teachers, trading and studying manuals, in the engine (phase 2 spec §10)."""

import systems.learning as learning
from engine.actions import Action, Choice
from systems.items import manual_price, manuals_of
from systems.purse import silver_of


class DealingsMixin:
    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        if npc.data.get("beast"):
            return extras
        if not learning.will_deal(self.world, npc.id, self.player.id):
            return extras
        if learning.can_ask_to_learn(self.world, npc.id, self.player.id) \
                and learning.will_teach(self.world, npc.id, self.player.id, self.place.id):
            extras.append(Choice("Ask to learn an art...", Action("learn_menu")))
        if learning.ensure_goods(self.world, npc.id):
            extras.append(Choice("Browse their manuals...", Action("browse")))
        return extras

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        if self.focus is not None:
            options["learn_menu"] = (self._lesson_choices(), Action("talk_menu"))
            options["browse"] = (self._goods_choices(), Action("talk_menu"))
        return options

    def _practise_extras(self, body) -> list:
        extras = super()._practise_extras(body)
        return extras + [Choice(f"Study the {m.name} (2 weeks)", Action("study", m.item.id))
                         for m in learning.unstudied(self.world, self.player.id)]

    def _lesson_choices(self) -> list[Choice]:
        choices = []
        for art in learning.teachable_arts(self.world, self.focus, self.player.id):
            price = learning.lesson_price(art)
            choices.append(Choice(f"Pay {price} silver to learn the {art.name}", Action("learn_paid", art.technique.id)))
            choices.append(Choice(f"Learn the {art.name} by passing a test spar", Action("learn_test", art.technique.id)))
        return choices

    def _goods_choices(self) -> list[Choice]:
        return [Choice(f"Buy the {m.name} ({manual_price(m)} silver)", Action("buy", m.item.id))
                for m in manuals_of(self.world, self.focus)]

    def _do_learn_menu(self, _target):
        if self.focus is None or not learning.can_ask_to_learn(self.world, self.focus, self.player.id) \
                or not learning.will_teach(self.world, self.focus, self.player.id, self.place.id):
            return self._turn([("No one here will teach you.", "system")])
        self.submenu = "learn_menu"
        return self._turn([("What would you learn?", "system")])

    def _do_browse(self, _target):
        if self.focus is None or not learning.will_deal(self.world, self.focus, self.player.id) \
                or not learning.ensure_goods(self.world, self.focus):
            return self._turn([("No one here is selling manuals.", "system")])
        self.submenu = "browse"
        return self._turn([("Which manual catches your eye?", "system")])

    def _do_learn_paid(self, technique_id):
        if self.focus is None or not learning.will_teach(self.world, self.focus, self.player.id, self.place.id):
            return self._turn([("Learn from whom?", "system")])
        events = learning.lesson_events(self.world, self.player.id, self.focus, self.place.id, technique_id, "silver")
        if not events:
            return self._turn([("They cannot teach you that.", "system")])
        if events[0].kind == "paid" and silver_of(self.world, self.player.id) < events[0].data["amount"]:
            return self._turn([("You cannot afford that lesson.", "system")])
        return self._turn(self._commit(events))

    def _do_learn_test(self, technique_id):
        if self.focus is None or not learning.will_teach(self.world, self.focus, self.player.id, self.place.id):
            return self._turn([("Learn from whom?", "system")])
        teachable = {a.technique.id for a in learning.teachable_arts(self.world, self.focus, self.player.id)}
        if technique_id not in teachable:
            return self._turn([("They cannot teach you that.", "system")])
        teacher = self.focus
        return self._turn(self._start_duel(teacher, "test", purpose={"teach": technique_id, "teacher": teacher}))

    def _do_buy(self, item_id):
        if self.focus is None or not learning.will_deal(self.world, self.focus, self.player.id):
            return self._turn([("Buy from whom?", "system")])
        events = learning.purchase_events(self.world, self.player.id, self.focus, self.place.id, item_id)
        if not events:
            return self._turn([("They don't have that.", "system")])
        if silver_of(self.world, self.player.id) < events[0].data["amount"]:
            return self._turn([("You cannot afford it.", "system")])
        return self._turn(self._commit(events))

    def _do_study(self, item_id):
        if busy := self._busy():
            return busy
        events = learning.study_events(self.world, self.player.id, self.place.id, item_id)
        return self._cultivated(events, "You have no such manual to study.")

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        purpose = data.get("purpose") or {}
        if data["mode"] == "test" and purpose.get("teach") and data["result"] == "passed":
            events = learning.lesson_events(self.world, self.player.id, purpose["teacher"], self.place.id, purpose["teach"], "test")
            if events:
                lines += self._commit(events)
        return lines
