"""Running your sect in the engine (phase 3c spec 5)."""

import systems.founding as founding
import systems.sect as sect_mod
from engine.actions import Action, Choice
from systems import halls
from systems.purse import silver_of

SECT_MENUS = ("sect", "sect_money")


class SectMixin:
    _disband_asked: bool = False

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        me = self.player.id
        if sect_mod.sect_of_member(self.world, me, npc.id) is not None:
            extras.insert(0, Choice("Sect matters...", Action("sect_menu")))
        elif sect_mod.can_invite(self.world, npc.id, me):
            extras.append(Choice("Invite them to your sect", Action("sect_invite", npc.id)))
        return extras

    def _faction_options(self, npc) -> list:
        options = super()._faction_options(npc)
        sect = founding.my_sect(self.world, self.player.id)
        if sect is None:
            return options
        for other in halls.recruits_for(self.world, npc.id):
            if self.world.entity(other).data["tier"] == "great" and not sect_mod.has_pact(self.world, sect, other) \
                    and sect_mod.sect_stance(self.world, other, sect) >= 0.5:
                options.append(Choice("Propose an alliance with your sect", Action("propose_pact", other)))
        return options

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        if self.focus is not None and self.submenu in SECT_MENUS:
            back = Action("talk_menu") if self.submenu == "sect" else Action("sect_menu")
            options[self.submenu] = (self._sect_choices(self.submenu), back)
        return options

    def _sect_choices(self, menu: str) -> list:
        world, me, person = self.world, self.player.id, self.focus
        sect = founding.my_sect(world, me)
        if sect is None:
            return []
        if menu == "sect_money":
            out = [Choice(f"Build a {name.replace('_', ' ')} ({cost} silver)", Action("sect_build", name))
                   for name, (cost, _) in sect_mod.BUILDINGS.items() if sect_mod.build_block(world, sect, name) is None]
            out += [Choice(f"Deposit {n} silver", Action("sect_treasury", n)) for n in (50, 200) if silver_of(world, me) >= n]
            if world.entity(sect).data["treasury"] >= 50:
                out.append(Choice("Withdraw 50 silver", Action("sect_treasury", -50)))
            out.append(Choice("Disband the sect" if not self._disband_asked else "Yes, disband it for good",
                              Action("sect_disband", self._disband_asked)))
            return out
        out = [Choice(f"Teach them the {world.entity(t).name}", Action("sect_teach", t))
               for t in sect_mod.teachable_to(world, me, person)[:2]]
        if sect_mod.elder_block(world, sect, person) is None and person not in sect_mod.members(world, sect, ("elder",)):
            out.append(Choice("Raise them to elder", Action("sect_elder", person)))
        out.append(Choice("Send them on sect duties", Action("sect_duty", person)))
        away = [p for p in sect_mod.members(world, sect) if world.entity(p).data.get("on_duty")]
        out += [Choice(f"Call back {world.entity(p).name}", Action("sect_duty", p)) for p in away[:2]]
        out.append(Choice("Treasury and buildings...", Action("sect_money")))
        out.append(Choice("Open the sect ledger", Action("ledger")))
        out.append(Choice("Expel them", Action("sect_expel", person)))
        return out

    def _sect_member_here(self) -> int | None:
        return sect_mod.sect_of_member(self.world, self.player.id, self.focus) if self.focus is not None else None

    def _do_sect_menu(self, _target):
        if self._sect_member_here() is None:
            return self._turn([("That is not sect business.", "system")])
        self.submenu = "sect"
        return self._turn([("What of the sect?", "system")])

    def _do_sect_money(self, _target):
        if self._sect_member_here() is None:
            return self._turn([("That is not sect business.", "system")])
        self.submenu = "sect_money"
        return self._turn([("The treasury and the halls.", "system")])

    def _do_sect_invite(self, npc):
        if self.focus != npc or not sect_mod.can_invite(self.world, npc, self.player.id):
            return self._turn([("They cannot join your sect.", "system")])
        return self._turn(self._commit(sect_mod.invite_events(self.world, self.player.id, npc, self.place.id)))

    def _do_sect_teach(self, technique):
        if self._sect_member_here() is None or technique not in sect_mod.teachable_to(self.world, self.player.id, self.focus):
            return self._turn([("You cannot teach them that.", "system")])
        self.submenu = None
        return self._turn(self._commit(sect_mod.teach_events(self.world, self.player.id, self.focus, technique, self.place.id)))

    def _do_sect_elder(self, person):
        sect = self._sect_member_here()
        if sect is None or person != self.focus:
            return self._turn([("That is not sect business.", "system")])
        if (why := sect_mod.elder_block(self.world, sect, person)) is not None:
            return self._turn([(why, "system")])
        self.submenu = None
        return self._turn(self._commit(sect_mod.elder_events(self.world, self.player.id, person, self.place.id)))

    def _do_sect_duty(self, person):
        sect = self._sect_member_here()
        if sect is None or person not in sect_mod.members(self.world, sect):
            return self._turn([("That is not sect business.", "system")])
        on = not self.world.entity(person).data.get("on_duty")
        if on and person == self.focus:
            self.focus = None
        self.submenu = None
        return self._turn(self._commit(sect_mod.duty_events(self.world, self.player.id, person, self.place.id, on)))

    def _do_sect_expel(self, person):
        if self._sect_member_here() is None or person != self.focus:
            return self._turn([("That is not sect business.", "system")])
        self.submenu, self.focus = None, None
        return self._turn(self._commit(sect_mod.expel_events(self.world, self.player.id, person, self.place.id)))

    def _do_sect_build(self, name):
        sect = self._sect_member_here()
        if sect is None:
            return self._turn([("That is not sect business.", "system")])
        if (why := sect_mod.build_block(self.world, sect, name)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(sect_mod.build_events(self.world, self.player.id, name, self.place.id)))

    def _do_sect_treasury(self, amount):
        sect = self._sect_member_here()
        if sect is None or not isinstance(amount, int) or amount == 0:
            return self._turn([("That is not sect business.", "system")])
        if amount > 0 and silver_of(self.world, self.player.id) < amount:
            return self._turn([(f"You don't have {amount} silver.", "system")])
        if amount < 0 and self.world.entity(sect).data["treasury"] < -amount:
            return self._turn([("The treasury cannot spare it.", "system")])
        return self._turn(self._commit(sect_mod.treasury_events(self.world, self.player.id, self.place.id, amount)))

    def _do_sect_disband(self, confirmed):
        if self._sect_member_here() is None:
            return self._turn([("That is not sect business.", "system")])
        if not confirmed or not self._disband_asked:
            self._disband_asked = True
            self.submenu = "sect_money"
            return self._turn([("Disband your sect? Choose again to confirm.", "system")])
        self._disband_asked, self.submenu, self.focus = False, None, None
        return self._turn(self._commit(sect_mod.disband_events(self.world, self.player.id, self.place.id)))

    def _do_propose_pact(self, other):
        sect = founding.my_sect(self.world, self.player.id)
        if sect is None or self.focus is None or other not in halls.recruits_for(self.world, self.focus) \
                or sect_mod.sect_stance(self.world, other, sect) < 0.5 or sect_mod.has_pact(self.world, sect, other):
            return self._turn([("They will not ally with you.", "system")])
        self.submenu = None
        return self._turn(self._commit(sect_mod.pact_events(self.world, self.player.id, self.focus, other, self.place.id)))
