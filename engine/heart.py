"""The dao heart in the engine (phase 5e spec 8): the heart page, oaths, respects at a grave, the heart trial at
a breakthrough, and amends and a smith's reading of a blade in conversation."""

import systems.blade_spirits as BS
import systems.demons as D
import systems.oaths as O
from engine.actions import Action, Choice
from engine.heart_page import heart_lines, oath_choices, rising_lines

HEART_MENUS = ("heart", "oath_menu", "heart_trial")
TALK_MENU = "heart_talk"


class HeartMixin:
    # --- choices -----------------------------------------------------------------------------------------------
    def _graves_here(self) -> list[int]:
        world, me, here = self.world, self.player.id, self.place.id
        return [d["whom"] for d in D.demons(world, me)
                if d["kind"] == "grief" and D.respects_block(world, me, d["whom"], here) is None]

    def _general_extras(self) -> list:
        extras = super()._general_extras()
        extras.append(Choice("Your heart", Action("heart")))
        extras += [Choice(f"Pay your respects to {self.world.entity(dead).name}", Action("pay_respects", dead))
                   for dead in self._graves_here()]
        return extras

    def _heart_talk(self, npc) -> list:
        world, me = self.world, self.player.id
        out = []
        if D.amends_block(world, me, npc.id) is None:
            out.append(Choice(f"Make amends ({D.AMENDS} silver)", Action("make_amends", npc.id)))
        item = BS.wielded(world, me)
        if item is not None and BS.tell_block(world, me, npc.id, item.id) is None:
            out.append(Choice(f"Have them look at {item.name}", Action("read_blade", npc.id)))
        return out

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        if self._heart_talk(npc):
            extras.append(Choice("Of the heart...", Action("heart_talk")))
        return extras

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        world, me = self.world, self.player.id
        if self.focus is not None:
            if self.submenu == TALK_MENU:
                options[TALK_MENU] = (self._heart_talk(world.entity(self.focus)), Action("talk_menu"))
            return options
        oaths = [Choice(label, Action("swear_oath", (kind, whom))) for label, kind, whom in oath_choices(world, me)]
        if self.submenu == "heart":
            choices = [Choice("Swear an oath...", Action("oath_menu"))] if oaths else []
            choices += [Choice(f"Pay your respects to {world.entity(dead).name}", Action("pay_respects", dead))
                        for dead in self._graves_here()]
            options["heart"] = (choices, Action("back"))
            options["oath_menu"] = (oaths, Action("heart"))  # typed "swear ..." reaches them from the heart page
        elif self.submenu == "oath_menu":
            options["oath_menu"] = (oaths, Action("heart"))
        elif self.submenu == "heart_trial" and D.rising(world, me) is not None:
            options["heart_trial"] = ([Choice("Face it", Action("heart_trial", "face")),
                                       Choice("Bury it and break through", Action("heart_trial", "bury")),
                                       Choice("Turn back", Action("heart_trial", "turn_back"))], Action("cultivate"))
        return options

    # --- the breakthrough -----------------------------------------------------------------------------------------
    def _heart_trial(self):
        """A demon rises at the gate of Second-rate or beyond: the trial comes before the breakthrough (spec 3)."""
        if D.rising(self.world, self.player.id) is None:
            return None
        self.submenu = "heart_trial"
        return self._turn(rising_lines(self.world, self.player.id))

    def _do_heart_trial(self, choice):
        if busy := self._busy():
            return busy
        events = D.trial_events(self.world, self.player.id, self.place.id, choice)
        if not events:
            return self._turn([("There is nothing at the gate to face.", "system")])
        return self._cultivated(events, "")

    # --- handlers ---------------------------------------------------------------------------------------------------
    def _do_heart(self, _target):
        self.submenu = "heart"
        return self._turn(heart_lines(self.world, self.player.id))

    def _do_oath_menu(self, _target):
        self.submenu = "oath_menu"
        return self._turn([("On your dao heart, you swear...", "system")])

    def _do_swear_oath(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        kind, whom = target if isinstance(target, tuple) and len(target) == 2 else (None, None)
        self.submenu = "heart"
        if (why := O.swear_block(world, me, kind, whom)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(O.swear_events(world, me, kind, whom, here)))

    def _do_pay_respects(self, dead):
        world, me, here = self.world, self.player.id, self.place.id
        if dead is None:
            dead = next(iter(self._graves_here()), None)
        if dead is None or (why := D.respects_block(world, me, dead, here)) is not None:
            return self._turn([("There is no grave of yours to kneel at here.", "system")])
        return self._turn(self._commit(D.respects_events(world, me, dead, here)))

    def _do_heart_talk(self, _target):
        if self.focus is None or not self._heart_talk(self.world.entity(self.focus)):
            return self._turn([("There is nothing of the heart to speak of with them.", "system")])
        self.submenu = TALK_MENU
        return self._turn([("What will you ask of them?", "system")])

    def _heart_deed(self, npc, why, events):
        if self.focus != npc:
            return self._turn([("They are not the one you are speaking with.", "system")])
        if why is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(events()))

    def _do_make_amends(self, npc):
        world, me, here = self.world, self.player.id, self.place.id
        why = D.amends_block(world, me, npc) if isinstance(npc, int) else "You owe them nothing."
        return self._heart_deed(npc, why, lambda: D.amends_events(world, me, npc, here))

    def _do_read_blade(self, npc):
        world, me, here = self.world, self.player.id, self.place.id
        item = BS.wielded(world, me)
        why = "You hold no blade." if item is None else BS.tell_block(world, me, npc, item.id)
        return self._heart_deed(npc, why, lambda: BS.tell_events(world, me, npc, item.id, here))
