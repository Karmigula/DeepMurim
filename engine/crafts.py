"""Forging and formations in the engine (phase 5d spec 7): the anvil, refining and masterworks, materials at the
smith's and from the slain, formations known and laid, smiths' and formation masters' wares and commissions, and
the Meet of Hammer and Furnace."""

import systems.craft_world as CW
import systems.forging as FG
import systems.formations as FM
import systems.gear as gear
import systems.materials as M
import systems.meet as MT
import systems.pills as P
from engine.actions import Action, Choice
from engine.crafts_page import crafts_lines, meet_lines

CRAFT_MENUS = ("crafts", "anvil", "masterwork", "meet")
TALK_MENU = "craft_talk"


def _distinct(items) -> list:
    seen, out = set(), []
    for item in items:
        if item.name not in seen:
            seen.add(item.name)
            out.append(item)
    return out


class CraftsMixin:
    _anvil: tuple = ()
    _naming: int | None = None

    @property
    def _slain_game(self) -> int | None:
        """A beast just slain here, kept with the hero (a reload keeps it; an heir has none)."""
        slain = self.world.entity(self.player.id).data.get("slain_game")
        return slain["beast"] if slain and slain.get("place") == self.place.id else None

    @_slain_game.setter
    def _slain_game(self, beast: int | None) -> None:
        self.world.update_data(self.player.id,
                               slain_game=None if beast is None else {"beast": beast, "place": self.place.id})

    # --- choices -----------------------------------------------------------------------------------------------
    def _general_extras(self) -> list:
        extras = super()._general_extras()
        world, me, here = self.world, self.player.id, self.place.id
        extras.append(Choice("Your crafts", Action("crafts")))
        if world.entity(here).kind == "town" or M.forge_of(world, me) is not None:
            extras.append(Choice("Work at the anvil", Action("anvil")))
        beast = self._slain_game
        if beast is not None:
            for part in M.PARTS:
                if M.parts_block(world, me, beast, part, here) is None:
                    word = "bones" if part == "bone" else "core"
                    extras.append(Choice(f"Take {world.entity(beast).name}'s {word}", Action("take_parts", part)))
        if MT.is_open(world, here):
            extras.append(Choice("The Meet of Hammer and Furnace", Action("meet")))
        return extras

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        if CW.crafter(self.world, npc.id) is not None:
            extras.append(Choice("Their craft...", Action("craft_talk")))
        return extras

    def _craft_talk(self, npc) -> list:
        world, me, here = self.world, self.player.id, self.place.id
        out = []
        if CW.crafter(world, npc.id) == "formation master":
            out.append(Choice(f"Buy {CW.FLAG_LOT} formation flags ({CW.FLAG_LOT * FM.FLAG_PRICE} silver)",
                              Action("buy_flags", npc.id)))
            for key in CW.teaches(world, npc.id):
                name = FM.PATTERNS[key]["name"]
                if FM.mastery(world, me, key) is None:
                    out.append(Choice(f"Buy a manual of {name} ({FM.manual_price(key)} silver)",
                                      Action("buy_manual", (npc.id, key))))
                if CW.commission_lay_block(world, me, npc.id, key, here) is None:
                    out.append(Choice(f"Have them lay {name} here ({CW.lay_price(key)} silver)",
                                      Action("commission_lay", (npc.id, key))))
        else:
            if CW.ready(world, me, npc.id) is not None:
                out.append(Choice("Collect what they forged for you", Action("collect_commission", npc.id)))
            grade = gear.GRADE_WORDS[CW.forge_grade(world, npc.id)]
            for slot, forms in FG.FORMS.items():
                for form in forms:
                    if CW.commission_forge_block(world, me, npc.id, slot, form, here) is None:
                        what = form if slot == "weapon" else gear.ARMOUR_WORDS[form]
                        out.append(Choice(f"Commission a {grade} {what} "
                                          f"({CW.forge_price(world, npc.id, here, slot)} silver)",
                                          Action("commission_forge", (npc.id, slot, form))))
        return out

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        world, me, here = self.world, self.player.id, self.place.id
        if self.focus is not None:
            if self.submenu == TALK_MENU:
                options[TALK_MENU] = (self._craft_talk(world.entity(self.focus)), Action("talk_menu"))
            return options
        if self.submenu == "smith" and "smith" in options:  # iron and a forge of one's own, at the smith's
            choices, back = options["smith"]
            more = [Choice(f"Buy {o['material']} ({M.price(world, here, o['material'])} silver)",
                           Action("buy_material", o["key"])) for o in _first_of_each(M.stock(world, here))]
            if M.buy_forge_block(world, me) is None:
                more.append(Choice(f"Buy an anvil and a forge ({M.FORGE_PRICE} silver)", Action("buy_forge")))
            options["smith"] = (more + choices, back)
        if self.submenu not in CRAFT_MENUS:
            return options
        choices = []
        if self.submenu == "crafts":
            for manual in _distinct(FM.manuals_of(world, me)):
                if FM.study_block(world, me, manual.id) is None:
                    choices.append(Choice(f"Study {manual.name}", Action("study_formation", manual.id)))
            for key in sorted(FM.known(world, me)):
                if FM.lay_block(world, me, key, here) is None:
                    choices.append(Choice(f"Lay {FM.PATTERNS[key]['name']} here ({FM.PATTERNS[key]['flags']} flags)",
                                          Action("lay_formation", key)))
            for item in gear.gear_items(world, me):
                if FG.masterwork_block(world, me, item.id) is None:
                    choices.append(Choice(f"Name {item.name}", Action("name_menu", item.id)))
        elif self.submenu == "anvil":
            anvil = [m for m in self._anvil if m in world.targets(me, "owns")]
            if anvil and M.forge_block(world, me, here) is None:
                for slot, forms in FG.FORMS.items():
                    for form in forms:
                        what = form if slot == "weapon" else gear.ARMOUR_WORDS[form]
                        grade = gear.GRADE_WORDS[FG.grade_of(world, me, form, anvil)]
                        choices.append(Choice(f"Forge a {grade} {what}", Action("forge", (slot, form))))
            if anvil:
                choices.append(Choice("Clear the anvil", Action("clear_anvil")))
            if len(anvil) < FG.MAX_MATERIALS:
                choices += [Choice(f"Put {m.name} on the anvil", Action("add_material", m.id))
                            for m in _distinct(m for m in M.materials_of(world, me) if m.id not in anvil)]
            for item in gear.gear_items(world, me):
                for m in _distinct(M.materials_of(world, me)):
                    if FG.refine_block(world, me, here, item.id, m.id) is None:
                        choices.append(Choice(f"Refine {item.name} with {m.name}", Action("refine_gear", (item.id, m.id))))
        elif self.submenu == "masterwork" and self._naming is not None:
            choices = [Choice(f"Name it {name}", Action("name_masterwork", name))
                       for name in FG.names_for(world, self._naming)]
        elif self.submenu == "meet":
            for craft in MT.CRAFTS:
                pieces = gear.gear_items(world, me) if craft == "forging" else P.pills_of(world, me)
                for piece in _distinct(pieces):
                    if MT.enter_block(world, me, craft, piece.id, here) is None:
                        choices.append(Choice(f"Show {piece.name} ({MT.score(world, me, craft, piece.id)})",
                                              Action("enter_meet", (craft, piece.id))))
        options[self.submenu] = (choices, Action("back"))
        return options

    # --- the world around ---------------------------------------------------------------------------------------
    def _after_arrival(self) -> list:
        self._slain_game, self._anvil = None, ()
        return super()._after_arrival()

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        entry = self.world.chronicle_entry(data["duel"]) if data.get("duel") else None
        if entry is not None and data.get("killed") and self.world.entity(entry.actors[1]).data.get("beast"):
            self._slain_game = entry.actors[1]
        return lines

    # --- handlers ---------------------------------------------------------------------------------------------------
    def _do_crafts(self, _target):
        self.submenu = "crafts"
        return self._turn(crafts_lines(self.world, self.player.id, self.place.id))

    def _do_anvil(self, _target):
        self.submenu = "anvil"
        anvil = [self.world.entity(m).name for m in self._anvil if m in self.world.targets(self.player.id, "owns")]
        lines = [("The anvil", "heading"), (f"  On it: {', '.join(anvil) if anvil else 'nothing'}", "dim")]
        if (why := M.forge_block(self.world, self.player.id, self.place.id)) is not None:
            lines.append((f"  {why}", "dim"))
        return self._turn(lines)

    def _do_add_material(self, item):
        world, me = self.world, self.player.id
        if M.material_info(world.entity(item) if isinstance(item, int) else None) is None \
                or item not in world.targets(me, "owns"):
            return self._turn([("You have no such material.", "system")])
        if item not in self._anvil and len(self._anvil) < FG.MAX_MATERIALS:
            self._anvil = self._anvil + (item,)
        return self._do_anvil(None)

    def _do_clear_anvil(self, _target):
        self._anvil, self.submenu = (), "anvil"
        return self._turn([("You take the materials back off the anvil.", "system")])

    def _do_forge(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        slot, form = target if isinstance(target, tuple) and len(target) == 2 else (None, None)
        anvil = [m for m in self._anvil if m in world.targets(me, "owns")]
        if slot is None or (why := FG.forge_block(world, me, here, slot, form, anvil)) is not None:
            return self._turn([(why if slot is not None else "Forge what?", "system")])
        self._anvil, self.submenu = (), "anvil"
        return self._turn(self._commit(FG.forge_events(world, me, here, slot, form, anvil)))

    def _do_refine_gear(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        item, material = target if isinstance(target, tuple) and len(target) == 2 else (None, None)
        self.submenu = "anvil"
        if item is None or (why := FG.refine_block(world, me, here, item, material)) is not None:
            return self._turn([(why if item is not None else "Refine what?", "system")])
        self._anvil = tuple(m for m in self._anvil if m != material)
        return self._turn(self._commit(FG.refine_events(world, me, here, item, material)))

    def _do_name_menu(self, item):
        if (why := FG.masterwork_block(self.world, self.player.id, item)) is not None:
            return self._turn([(why, "system")])
        self._naming, self.submenu = item, "masterwork"
        return self._turn([(f"What will you call {self.world.entity(item).name}?", "system")])

    def _do_name_masterwork(self, name):
        world, me, item = self.world, self.player.id, self._naming
        if item is None or (why := FG.masterwork_block(world, me, item)) is not None \
                or name not in FG.names_for(world, item):
            return self._turn([("There is nothing to name.", "system")])
        self._naming = None
        return self._turn(self._commit(FG.masterwork_events(world, me, item, name, self.place.id)))

    def _do_buy_material(self, key):
        world, me, here = self.world, self.player.id, self.place.id
        self.submenu = "smith"
        if not isinstance(key, str) or (why := M.buy_block(world, me, here, key)) is not None:
            return self._turn([(why if isinstance(key, str) else "The smith has none of that.", "system")])
        return self._turn(self._commit(M.buy_events(world, me, here, key)))

    def _do_buy_forge(self, _target):
        self.submenu = "smith"
        if (why := M.buy_forge_block(self.world, self.player.id)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(M.buy_forge_events(self.world, self.player.id, self.place.id)))

    def _do_take_parts(self, part):
        world, me, here = self.world, self.player.id, self.place.id
        beast = self._slain_game
        if beast is None or (why := M.parts_block(world, me, beast, part, here)) is not None:
            return self._turn([("There is nothing to take.", "system")])
        return self._turn(self._commit(M.parts_events(world, me, beast, part, here)))

    def _do_study_formation(self, item):
        world, me = self.world, self.player.id
        if item is None:
            item = next((m.id for m in FM.manuals_of(world, me) if FM.study_block(world, me, m.id) is None), None)
        self.submenu = "crafts"
        if item is None or (why := FM.study_block(world, me, item)) is not None:
            return self._turn([(why if item is not None else "You have no manual to study.", "system")])
        return self._turn(self._commit(FM.study_events(world, me, item, self.place.id)))

    def _do_lay_formation(self, key):
        world, me, here = self.world, self.player.id, self.place.id
        self.submenu = "crafts"
        if not isinstance(key, str) or (why := FM.lay_block(world, me, key, here)) is not None:
            return self._turn([(why if isinstance(key, str) else "Lay what?", "system")])
        return self._turn(self._commit(FM.lay_events(world, me, key, here)))

    def _do_meet(self, _target):
        if not MT.is_open(self.world, self.place.id):
            return self._turn([("The Meet is not held here now.", "system")])
        self.submenu = "meet"
        return self._turn(meet_lines(self.world))

    def _do_enter_meet(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        craft, item = target if isinstance(target, tuple) and len(target) == 2 else (None, None)
        self.submenu = "meet"
        if craft is None or (why := MT.enter_block(world, me, craft, item, here)) is not None:
            return self._turn([(why if craft is not None else "Show what?", "system")])
        return self._turn(self._commit(MT.enter_events(world, me, craft, item, here)) + meet_lines(world))

    # --- in conversation -------------------------------------------------------------------------------------------
    def _do_craft_talk(self, _target):
        if self.focus is None or CW.crafter(self.world, self.focus) is None:
            return self._turn([("They have no craft to speak of.", "system")])
        self.submenu = TALK_MENU
        told = f"{self.world.entity(self.focus).name} is {CW.title(self.world, self.focus)}."
        return self._turn([(told, "dim"), ("What will you ask of them?", "system")])

    def _craft_deed(self, npc, why, events):
        if self.focus != npc:
            return self._turn([("They are not the one you are speaking with.", "system")])
        if why is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(events()))

    def _do_buy_flags(self, npc):
        world, me, here = self.world, self.player.id, self.place.id
        return self._craft_deed(npc, CW.flags_block(world, me, npc), lambda: CW.flags_events(world, me, npc, here))

    def _do_buy_manual(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        npc, key = target if isinstance(target, tuple) and len(target) == 2 else (None, None)
        return self._craft_deed(npc, CW.manual_block(world, me, npc, key) if npc else "They sell nothing.",
                               lambda: CW.manual_events(world, me, npc, key, here))

    def _do_commission_lay(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        npc, key = target if isinstance(target, tuple) and len(target) == 2 else (None, None)
        return self._craft_deed(npc, CW.commission_lay_block(world, me, npc, key, here) if npc else "They lay nothing.",
                               lambda: CW.commission_lay_events(world, me, npc, key, here))

    def _do_commission_forge(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        npc, slot, form = target if isinstance(target, tuple) and len(target) == 3 else (None, None, None)
        return self._craft_deed(npc, CW.commission_forge_block(world, me, npc, slot, form, here) if npc
                               else "They forge nothing.",
                               lambda: CW.commission_forge_events(world, me, npc, slot, form, here))

    def _do_collect_commission(self, npc):
        world, me, here = self.world, self.player.id, self.place.id
        why = None if isinstance(npc, int) and CW.ready(world, me, npc) is not None else "Nothing of yours is ready."
        return self._craft_deed(npc, why, lambda: CW.collect_events(world, me, npc, here))


def _first_of_each(offers: list[dict]) -> list[dict]:
    seen, out = set(), []
    for o in offers:
        if o["material"] not in seen:
            seen.add(o["material"])
            out.append(o)
    return out
