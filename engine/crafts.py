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

CRAFT_MENUS = ("crafts", "anvil", "forge_menu", "refine_menu", "lay_menu", "masterwork", "meet")
BACK = {"forge_menu": "anvil", "refine_menu": "anvil", "lay_menu": "crafts"}
TALK_MENU = "craft_talk"
TALK_MENUS = {TALK_MENU: "talk_menu", "craft_manuals": TALK_MENU, "craft_lay": TALK_MENU}  # and where Back goes


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

    def _manuals(self, npc) -> list:
        world, me = self.world, self.player.id
        return [Choice(f"Buy a manual of {FM.PATTERNS[key]['name']} ({FM.manual_price(key)} silver)",
                       Action("buy_manual", (npc.id, key)))
                for key in CW.teaches(world, npc.id) if FM.mastery(world, me, key) is None]

    def _lays(self, npc) -> list:
        world, me, here = self.world, self.player.id, self.place.id
        return [Choice(f"Have them lay {FM.PATTERNS[key]['name']} here ({CW.lay_price(key)} silver)",
                       Action("commission_lay", (npc.id, key)))
                for key in CW.teaches(world, npc.id) if CW.commission_lay_block(world, me, npc.id, key, here) is None]

    def _craft_talk(self, npc) -> list:
        """A master's wares, a menu each: seven patterns of manuals and lays would not fit on one screen."""
        world, me, here = self.world, self.player.id, self.place.id
        out = []
        if CW.crafter(world, npc.id) == "formation master":
            out.append(Choice(f"Buy {CW.FLAG_LOT} formation flags ({CW.FLAG_LOT * FM.FLAG_PRICE} silver)",
                              Action("buy_flags", npc.id)))
            if self._manuals(npc):
                out.append(Choice("Their manuals...", Action("craft_menu", "craft_manuals")))
            if self._lays(npc):
                out.append(Choice("Have them lay a formation...", Action("craft_menu", "craft_lay")))
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
            if self.submenu in TALK_MENUS:
                npc = world.entity(self.focus)
                build = {TALK_MENU: self._craft_talk, "craft_manuals": self._manuals, "craft_lay": self._lays}
                options[self.submenu] = (build[self.submenu](npc), Action(TALK_MENUS[self.submenu]))
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
        inner = {name: build() for name, build in (("forge_menu", self._forge_choices),
                                                   ("refine_menu", self._refine_choices),
                                                   ("lay_menu", self._lay_choices))
                 if self.submenu in (name, BACK[name])}  # only the menus this screen shows or opens
        if self.submenu == "crafts":
            if inner["lay_menu"]:
                choices.append(Choice("Lay a formation here...", Action("craft_menu", "lay_menu")))
            for item in gear.gear_items(world, me):
                if FG.masterwork_block(world, me, item.id) is None:
                    choices.append(Choice(f"Name {item.name}", Action("name_menu", item.id)))
            for manual in _distinct(FM.manuals_of(world, me)):
                if FM.study_block(world, me, manual.id) is None:
                    choices.append(Choice(f"Study {manual.name}", Action("study_formation", manual.id)))
        elif self.submenu == "anvil":  # the forms and the refining each on a menu of their own (seven forms)
            anvil = self._on_anvil()
            if inner["forge_menu"]:
                choices.append(Choice("Forge...", Action("craft_menu", "forge_menu")))
            if inner["refine_menu"]:
                choices.append(Choice("Refine a piece...", Action("craft_menu", "refine_menu")))
            if len(anvil) < FG.MAX_MATERIALS:
                choices += [Choice(f"Put {m.name} on the anvil", Action("add_material", m.id))
                            for m in _distinct(m for m in M.materials_of(world, me) if m.id not in anvil)]
            if anvil:
                choices.append(Choice("Clear the anvil", Action("clear_anvil")))
        elif self.submenu in inner:
            choices = inner[self.submenu]
        elif self.submenu == "masterwork" and self._naming is not None:
            choices = [Choice(f"Name it {name}", Action("name_masterwork", name))
                       for name in FG.names_for(world, self._naming)]
        elif self.submenu == "meet":  # the best pieces first: many pills would run off the menu
            shows = []
            for craft in MT.CRAFTS:
                pieces = gear.gear_items(world, me) if craft == "forging" else P.pills_of(world, me)
                for piece in _distinct(pieces):
                    if MT.enter_block(world, me, craft, piece.id, here) is None:
                        shows.append((MT.score(world, me, craft, piece.id), craft, piece))
            shows.sort(key=lambda s: (-s[0], s[1], s[2].id))
            choices = [Choice(f"Show {piece.name} ({score})", Action("enter_meet", (craft, piece.id)))
                       for score, craft, piece in shows]
        for name, found in inner.items():  # an inner menu's choices stay reachable by typing from its outer menu
            options[name] = (found, Action(BACK[name]))
        options[self.submenu] = (choices, Action(BACK.get(self.submenu, "back")))
        return options

    def _on_anvil(self) -> list:
        return [m for m in self._anvil if m in self.world.targets(self.player.id, "owns")]

    def _forge_choices(self) -> list:
        world, me, here = self.world, self.player.id, self.place.id
        anvil = self._on_anvil()
        if not anvil or M.forge_block(world, me, here) is not None:
            return []
        out = []
        for slot, forms in FG.FORMS.items():
            for form in forms:
                what = form if slot == "weapon" else gear.ARMOUR_WORDS[form]
                grade = gear.GRADE_WORDS[FG.grade_of(world, me, form, anvil)]
                out.append(Choice(f"Forge a {grade} {what}", Action("forge", (slot, form))))
        return out

    def _refine_choices(self) -> list:
        world, me, here = self.world, self.player.id, self.place.id
        return [Choice(f"Refine {item.name} with {m.name}", Action("refine_gear", (item.id, m.id)))
                for item in gear.gear_items(world, me) for m in _distinct(M.materials_of(world, me))
                if FG.refine_block(world, me, here, item.id, m.id) is None]

    def _lay_choices(self) -> list:
        world, me, here = self.world, self.player.id, self.place.id
        return [Choice(f"Lay {FM.PATTERNS[key]['name']} here ({FM.PATTERNS[key]['flags']} flags)",
                       Action("lay_formation", key))
                for key in sorted(FM.known(world, me)) if FM.lay_block(world, me, key, here) is None]

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
    def _do_craft_menu(self, menu):
        """One of the crafts' inner menus: the forms, the refining, the lays; a master's manuals and lays."""
        if menu in TALK_MENUS and menu != TALK_MENU and self.focus is not None \
                and CW.crafter(self.world, self.focus) == "formation master":
            self.submenu = menu
            return self._turn([])
        if menu in BACK and self.focus is None:
            self.submenu = menu
            return self._turn([])
        return self._turn([("There is no such menu.", "system")])

    def _do_crafts(self, _target):
        self.submenu = "crafts"
        return self._turn(crafts_lines(self.world, self.player.id, self.place.id))

    def _do_anvil(self, _target):
        self.submenu = "anvil"
        anvil = [self.world.entity(m).name for m in self._on_anvil()]
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
        anvil = self._on_anvil()
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
        world, npc = self.world, self.focus
        lines = [(f"{world.entity(npc).name} is {CW.title(world, npc)}.", "dim")]
        for c in CW.pending(world, self.player.id):  # what they are forging for you, and when it is ready
            if c["smith"] == npc and c["ready_at"] > world.time:
                days = -(-(c["ready_at"] - world.time) // 4)
                lines.append((f"Your {gear.GRADE_WORDS[c['grade']]} {gear.ARMOUR_WORDS.get(c['form'], c['form'])} "
                              f"will be ready in {days} day(s).", "dim"))
        return self._turn(lines + [("What will you ask of them?", "system")])

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
