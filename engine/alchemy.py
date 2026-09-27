"""Alchemy, medicine and poison in the engine (phase 5b spec 5): the page and its menu, the herbalist, gathering,
the furnace's tray, refining, pills, baths, venom, sealing and forcing out, a venomous beast's spoils, and death
by poison."""

import systems.alchemy as A
import systems.encounters as encounters
import systems.herbs as H
import systems.pills as P
import systems.poison_path as PP
import systems.toxins as X
from engine.actions import Action, Choice
from engine.alchemy_page import alchemy_lines
from systems.bodies import load_body
from world.body import PHYSIQUE
from world.gen.materialize import region_of

ALCHEMY_MENUS = ("alchemy", "herbalist", "bath")


def _distinct(items) -> list:
    """One of each kind: herbs and pills alike are told apart by name (a menu lists each once)."""
    seen, out = set(), []
    for item in items:
        if item.name not in seen:
            seen.add(item.name)
            out.append(item)
    return out


class AlchemyMixin:
    _tray: tuple = ()
    _slain_beast: int | None = None

    # --- choices -----------------------------------------------------------------------------------------------
    def _general_extras(self) -> list:
        extras = super()._general_extras()
        world, me, here = self.world, self.player.id, self.place.id
        extras.append(Choice("Your alchemy", Action("alchemy")))
        if H.gather_block(world, me, here) is None:
            extras.append(Choice("Search the surroundings for herbs", Action("gather")))
        if world.entity(here).kind == "town":
            extras.append(Choice("Visit the herbalist", Action("herbalist")))
        body = load_body(world, me)
        if X.seal_block(body, world.time) is None:
            extras.append(Choice("Seal your acupoints against the poison", Action("seal")))
        if X.force_block(body) is None:
            extras.append(Choice("Force the poison out with your qi", Action("force_out")))
        beast = self._slain_beast
        if beast is not None and PP.butcher_block(world, me, beast, here) is None:
            name = world.entity(beast).name
            extras.append(Choice(f"Drink {name}'s blood", Action("butcher", "blood")))
            extras.append(Choice(f"Take {name}'s inner core", Action("butcher", "core")))
        pills = P.pills_of(world, me)
        if any(P.effect_of(p) == "tempering" for p in pills):
            extras.append(Choice("Take a tempering bath...", Action("bath_menu")))
        venom = next((p for p in pills if P.effect_of(p) == "venom"), None)
        if venom is not None and P.coat_block(world, me, venom.id) is None:
            extras.append(Choice("Coat your blade with venom", Action("coat", venom.id)))
        return extras

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        if PP.art_block(self.world, self.player.id, npc.id) is None:
            extras.append(Choice(f"Buy a poison art's manual ({PP.ART_PRICE} silver)", Action("buy_poison_art", npc.id)))
        return extras

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        if self.focus is not None or self.submenu not in ALCHEMY_MENUS:
            return options
        world, me, here = self.world, self.player.id, self.place.id
        if self.submenu == "alchemy":  # the furnace first; each kind of herb and pill once (5b review)
            choices = []
            tray = [t for t in self._tray if t in world.targets(me, "owns")]
            if len(tray) >= A.MIN_HERBS:
                choices.append(Choice(f"Light the furnace ({len(tray)} herbs)", Action("experiment")))
            if tray:
                choices.append(Choice("Empty the furnace", Action("empty_furnace")))
            for recipe, _ in A.known_recipes(world, me):
                if A.find_batch(world, me, recipe) is not None:
                    choices.append(Choice(f"Refine {world.entity(recipe).name}", Action("refine", recipe)))
            herbs = H.herbs_of(world, me)
            if len(tray) < A.MAX_HERBS:
                choices += [Choice(f"Put {H.herb_name(*H.herb_info(h))} in the furnace", Action("add_herb", h.id))
                            for h in _distinct(h for h in herbs if h.id not in tray)]
            choices += [Choice(f"Swallow {p.name}", Action("swallow", p.id))
                        for p in _distinct(p for p in P.pills_of(world, me) if P.swallow_block(world, me, p.id) is None)]
            choices += [Choice(f"Taste {H.herb_name(*H.herb_info(h))}", Action("taste", h.id)) for h in _distinct(herbs)]
            options["alchemy"] = (choices, Action("back"))
        elif self.submenu == "herbalist":
            choices = [Choice(f"Buy a bronze furnace ({H.FURNACE_PRICE} silver)", Action("buy_furnace"))] \
                if H.furnace_block(world, me) is None else []
            choices += [Choice(f"Buy {H.herb_name(o['herb'], o['grade'])} ({H.price(world, here, o['herb'], o['grade'])} "
                               f"silver)", Action("buy_herb", o["key"])) for o in H.stock(world, here)]
            options["herbalist"] = (choices, Action("back"))
        else:
            choices = [Choice(f"Temper your {stat}", Action("bathe", stat)) for stat in PHYSIQUE]
            if load_body(world, me).constitution is None:
                for herb in _distinct(h for h in H.herbs_of(world, me) if H.herb_info(h)[1] >= 3):
                    name = H.herb_info(herb)[0]
                    choices += [Choice(f"Temper your {stat} with {name}", Action("bathe", (stat, herb.id)))
                                for stat in PHYSIQUE]
            options["bath"] = (choices, Action("back"))
        return options

    # --- the world around ---------------------------------------------------------------------------------------
    def _after_arrival(self) -> list:
        self._slain_beast = None
        return super()._after_arrival()

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        entry = self.world.chronicle_entry(data["duel"]) if data.get("duel") else None
        if entry is not None and data.get("killed") and self.world.entity(entry.actors[1]).data.get("venomous"):
            self._slain_beast = entry.actors[1]
        return lines

    def _after_turn(self, turn):
        """After the whole deed, not in the middle of it: a poison that has outlasted you is your death (spec 4.2)."""
        turn = super()._after_turn(turn)
        if self.player.data.get("dying") or self.player.data.get("dead"):
            return turn
        deaths = X.death_events(self.world, self.player.id)
        if not deaths:
            return turn
        lines = self._commit(deaths) + self._death_lines()
        return self._turn(list(turn.lines) + lines)

    # --- handlers -----------------------------------------------------------------------------------------------
    def _do_alchemy(self, _target):
        self.submenu = "alchemy"
        return self._turn(alchemy_lines(self.world, self.player.id, list(self._tray)))

    def _do_herbalist(self, _target):
        self.submenu = "herbalist"
        return self._turn([(f"The herbalist of {self.place.name}", "heading")])

    def _do_bath_menu(self, _target):
        self.submenu = "bath"
        return self._turn([("Which part of your body will the bath temper?", "system")])

    def _do_gather(self, _target):
        world, me, here = self.world, self.player.id, self.place.id
        if (why := H.gather_block(world, me, here)) is not None:
            return self._turn([(why, "system")])
        events = H.gather_events(world, me, here)
        lines = self._commit(events)
        if events[0].data["guarded"]:  # a beast guards the best of it (spec 2.3)
            region = region_of(world, here)
            beast = encounters.make_roamer(world, region, "beast", encounters._free_roamer_slot(world, region), 0.5)
            met = encounters.encounter_events(me, beast, here, "beast", 0)
            lines += self._commit(met)
            self.encounter = encounters.encounter_state(met[0])
        return self._turn(lines)

    def _do_taste(self, item):
        if (why := H.taste_block(self.world, self.player.id, item)) is not None:
            return self._turn([(why, "system")])
        self.submenu = "alchemy"
        return self._turn(self._commit(H.taste_events(self.world, self.player.id, item, self.place.id)))

    def _do_add_herb(self, item):
        if H.herb_info(self.world.entity(item) if isinstance(item, int) else None) is None \
                or item not in self.world.targets(self.player.id, "owns"):
            return self._turn([("You have no such herb.", "system")])
        if item not in self._tray and len(self._tray) < A.MAX_HERBS:
            self._tray = self._tray + (item,)
        self.submenu = "alchemy"
        return self._turn(alchemy_lines(self.world, self.player.id, list(self._tray)))

    def _do_empty_furnace(self, _target):
        self._tray, self.submenu = (), "alchemy"
        return self._turn([("You tip the herbs back out.", "system")])

    def _do_experiment(self, _target):
        world, me, here = self.world, self.player.id, self.place.id
        tray = [t for t in self._tray if t in world.targets(me, "owns")]
        if (why := A.experiment_block(world, me, here, tray)) is not None:
            return self._turn([(why, "system")])
        self._tray, self.submenu = (), "alchemy"
        return self._turn(self._commit(A.experiment_events(world, me, here, tray)))

    def _do_refine(self, recipe):
        world, me, here = self.world, self.player.id, self.place.id
        batch = A.find_batch(world, me, recipe) if isinstance(recipe, int) else None
        if batch is None:
            return self._turn([("You have not the herbs for it.", "system")])
        if (why := A.refine_block(world, me, here, recipe, batch)) is not None:
            return self._turn([(why, "system")])
        self.submenu = "alchemy"
        return self._turn(self._commit(A.refine_events(world, me, here, recipe, batch)))

    def _do_swallow(self, item):
        world, me = self.world, self.player.id
        if item is None:  # typed: the first pill one can swallow, never a poison (only named, it is drunk)
            item = next((p.id for p in P.pills_of(world, me)
                         if P.effect_of(p) != "poison" and P.swallow_block(world, me, p.id) is None), None)
        if item is None or (why := P.swallow_block(world, me, item)) is not None:
            return self._turn([(why if item is not None else "You have no pill to swallow.", "system")])
        return self._turn(self._commit(P.swallow_events(world, me, self.place.id, item)))

    def _do_coat(self, item):
        if (why := P.coat_block(self.world, self.player.id, item)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(P.coat_events(self.world, self.player.id, self.place.id, item)))

    def _do_buy_herb(self, key):
        world, me, here = self.world, self.player.id, self.place.id
        self.submenu = "herbalist"
        if (why := H.buy_block(world, me, here, key)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(H.buy_events(world, me, here, key)))

    def _do_buy_furnace(self, _target):
        if (why := H.furnace_block(self.world, self.player.id)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(H.furnace_events(self.world, self.player.id, self.place.id)))

    def _do_seal(self, _target):
        if (why := X.seal_block(load_body(self.world, self.player.id), self.world.time)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(X.seal_events(self.world, self.player.id, self.place.id)))

    def _do_force_out(self, _target):
        if (why := X.force_block(load_body(self.world, self.player.id))) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(X.force_events(self.world, self.player.id, self.place.id)))

    def _do_butcher(self, part):
        beast = self._slain_beast
        if beast is None or part not in ("blood", "core") \
                or (why := PP.butcher_block(self.world, self.player.id, beast, self.place.id)) is not None:
            return self._turn([("There is nothing to take.", "system")])
        return self._turn(self._commit(PP.butcher_events(self.world, self.player.id, beast, self.place.id, part)))

    def _do_bathe(self, stat):
        world, me, here = self.world, self.player.id, self.place.id
        stat, herb = stat if isinstance(stat, tuple) else (stat, None)
        draught = next((p.id for p in P.pills_of(world, me) if P.effect_of(p) == "tempering"), None)
        if (why := PP.bath_block(world, me, here, stat, draught)) is not None:
            return self._turn([(why, "system")])
        if herb is not None and (herb not in world.targets(me, "owns") or H.herb_info(world.entity(herb)) is None):
            return self._turn([("You have no such herb.", "system")])
        return self._turn(self._commit(PP.bath_events(world, me, here, stat, draught, herb)))

    def _do_buy_poison_art(self, npc):
        if self.focus != npc or (why := PP.art_block(self.world, self.player.id, npc)) is not None:
            return self._turn([("They teach no poisons.", "system")])
        return self._turn(self._commit(PP.art_events(self.world, self.player.id, npc, self.place.id)))
