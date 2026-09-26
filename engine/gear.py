"""Weapons and armour in the engine (phase 5a spec 5): the inventory, the smith, the armoury, the fallen's gear,
the blades people know, and duels for a weapon."""

import systems.armoury as armoury
import systems.encounters as encounters
import systems.famous as FW
import systems.gear as gear
import systems.provenance as provenance
import systems.smithy as smithy
import systems.spoils as spoils
from engine.actions import Action, Choice
from engine.gear_page import chronicle_lines, inventory_lines, item_lines
from world.events import commit
from world.gen.materialize import people_at

GEAR_MENUS = ("gear", "smith")


class GearMixin:
    _beaten: int | None = None
    _demand: tuple | None = None
    _stake: tuple | None = None
    _covet_asked: frozenset = frozenset()  # who has already called you out for your blade since you came here
    _demanded: frozenset = frozenset()  # the blades already asked back since you came here

    # --- choices ---------------------------------------------------------------------------------------------
    def _general_extras(self) -> list:
        extras = super()._general_extras()
        world, me, here = self.world, self.player.id, self.place.id
        extras.append(Choice("Your gear", Action("inventory")))
        extras.append(Choice("Visit the smith", Action("smith")))
        for faction in world.entity(here).data.get("seats", []):
            for slot, what in (("weapon", "a weapon"), ("armour", "armour")):
                if armoury.draw_block(world, me, faction, slot, here) is None:
                    extras.append(Choice(f"Draw {what} from the {world.entity(faction).name}'s armoury",
                                         Action("draw_gear", (faction, slot))))
        loser = self._beaten
        if loser is not None and world.entity(loser) is not None:
            for slot, what in (("weapon", "weapon"), ("armour", "armour")):
                if spoils.take_block(world, me, loser, slot, here) is None:
                    extras.append(Choice(f"Take {world.entity(loser).name}'s {what}", Action("take_gear", (loser, slot))))
        for item in FW.lying_at(world, here):
            extras.append(Choice(f"Take up {world.entity(item).name}, lying here", Action("take_lying", item)))
        if self._demand is not None:
            demander, item = self._demand
            name = world.entity(item).name
            extras.append(Choice(f"Hand {name} over to {world.entity(demander).name}", Action("answer_demand", True)))
            extras.append(Choice(f"Refuse to give up {name}", Action("answer_demand", False)))
        return extras

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        item = gear.item_in(self.world, npc.id, "weapon")
        if item is not None and item.data.get("famous") and not npc.data.get("beast"):
            extras.append(Choice(f"Challenge them for {item.name}", Action("duel_for_weapon", (npc.id, item.id))))
        return extras

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        if self.focus is not None or self.submenu not in GEAR_MENUS:
            return options
        world, me, here = self.world, self.player.id, self.place.id
        if self.submenu == "gear":
            choices = []
            for item in gear.gear_items(world, me):
                slot = item.data["slot"]
                held = gear.item_in(world, me, slot)
                if held is None or held.id != item.id:
                    choices.append(Choice(f"{'Wield' if slot == 'weapon' else 'Wear'} {item.name}", Action("wield", item.id)))
                else:
                    choices.append(Choice(f"Put away {item.name}", Action("put_away", slot)))
                choices.append(Choice(f"Inspect {item.name}", Action("inspect", item.id)))
                if item.data.get("armoury") is not None and world.entity(item.data["armoury"]).data.get("seat") == here:
                    choices.append(Choice(f"Return {item.name} to the armoury", Action("return_gear", item.id)))
                if FW.return_block(world, me, item.id, here) is None:
                    choices.append(Choice(f"Give {item.name} back to its clan", Action("return_heirloom", item.id)))
            if gear.item_in(world, me, "weapon") is None and gear.weapon_of(world, me) is not None:
                choices.append(Choice("Inspect your weapon", Action("inspect", None)))
            options["gear"] = (choices, Action("back"))
        else:
            choices = [Choice(f"Buy {gear.gear_name(o['slot'], o['form'], o['grade'])} "
                              f"({smithy.price(world, here, o['slot'], o['grade'])} silver)", Action("buy_gear", o["key"]))
                       for o in smithy.stock(world, here)]
            for item in gear.gear_items(world, me):
                if smithy.sell_block(world, me, here, item.id) is None:
                    choices.append(Choice(f"Sell {item.name} ({smithy.sell_price(world, here, item.id)} silver)",
                                          Action("sell_gear", item.id)))
            options["smith"] = (choices, Action("back"))
        return options

    # --- the scene: blades known ----------------------------------------------------------------------------
    def _blade_reactions(self) -> list:
        world, me, here = self.world, self.player.id, self.place.id
        if gear.item_in(world, me, "weapon") is None or self.combat is not None:
            return []
        present = [p.id for p in people_at(world, here, exclude=me)]
        seen = provenance.reactions(world, me, here, present)
        item = gear.item_in(world, me, "weapon").id
        lines = []
        if seen["hates"]:
            commit(world, provenance.hatred_events(world, me, seen["hates"], here, item))
            names = ", ".join(world.entity(h).name for h in seen["hates"])
            lines.append((f"{names} know{'s' if len(seen['hates']) == 1 else ''} the blade you carry, and whose blood is on it.", "red"))
        if seen["demands"] is not None and self._demand is None and item not in self._demanded:
            self._demand, self._demanded = (seen["demands"], item), self._demanded | {item}
            lines.append((f"{world.entity(seen['demands']).name} knows {world.entity(item).name}: "
                          "their sect calls it its own, and wants it back.", "system"))
        if seen["covets"] is not None and seen["covets"] not in self._covet_asked                 and self.challenger is None and self.encounter is None:
            npc = seen["covets"]
            self._covet_asked = self._covet_asked | {npc}
            lines += self._commit(encounters.challenge_events(me, npc, here))
            self.challenger, self._stake = npc, (npc, item)
            lines.append((f"{world.entity(npc).name} wants {world.entity(item).name}, and will fight you for it.", "system"))
        return lines

    def _after_arrival(self) -> list:
        self._beaten, self._demand, self._covet_asked, self._demanded = None, None, frozenset(), frozenset()
        self._stake = None  # a challenge dodged by leaving does not follow you
        return super()._after_arrival() + self._blade_reactions()

    def _after_look(self) -> list:
        return super()._after_look() + self._blade_reactions()

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        entry = self.world.chronicle_entry(data["duel"]) if data.get("duel") else None
        if entry is None or len(entry.actors) < 2:
            return lines
        me, opponent = entry.actors[0], entry.actors[1]
        won = data.get("result") == "won"
        for later in self.world.chronicle_about(me, limit=6):  # a victor who took your blade (spoils)
            if later.kind == "gear_passed" and later.id > entry.id and later.data.get("giver") == me \
                    and later.data.get("taker") == opponent:
                lines.append((f"{self.world.entity(opponent).name} takes {self.world.entity(later.data['item']).name} "
                              "from you.", "red"))
        if won:
            self._beaten = opponent
        purpose = data.get("purpose") or {}
        stake = purpose.get("weapon")
        if stake is not None and won and stake in self.world.targets(opponent, "owns"):
            lines += self._commit(gear.pass_events(self.world, opponent, me, stake, self.place.id, "won"))
        if self._stake is not None and self._stake[0] == opponent:
            item = self._stake[1]
            if data.get("by") == "opponent" and item in self.world.targets(me, "owns"):
                lines += self._commit(gear.pass_events(self.world, me, opponent, item, self.place.id, "won"))
            self._stake = None
        return lines

    # --- handlers -------------------------------------------------------------------------------------------
    def _do_inventory(self, _target):
        self.submenu = "gear"
        return self._turn(inventory_lines(self.world, self.player.id) + chronicle_lines(self.world, self.player.id))

    def _do_smith(self, _target):
        self.submenu = "smith"
        lines = [(f"The smith's stall ({smithy.smith_name(self.world, self.place.id)})", "heading")]
        if not smithy.stock(self.world, self.place.id):
            lines.append(("Nothing left this season.", "dim"))
        return self._turn(lines)

    def _do_wield(self, item_id):
        world, me = self.world, self.player.id
        item = world.entity(item_id) if isinstance(item_id, int) else None
        slot = item.data["slot"] if item is not None and item.kind == "gear" else "weapon"
        if (why := gear.fits(world, me, item_id, slot)) is not None:
            return self._turn([(why, "system")])
        self.submenu = "gear"
        return self._turn(self._commit(gear.wield_events(world, me, item_id, self.place.id)))

    def _do_put_away(self, slot):
        self.submenu = "gear"
        events = gear.put_away_events(self.world, self.player.id, slot if slot in gear.SLOTS else "weapon", self.place.id)
        return self._turn(self._commit(events) if events else [("You hold nothing of the kind.", "system")])

    def _do_inspect(self, item_id):
        world, me = self.world, self.player.id
        if item_id is None:  # the plain weapon you carry: looking at it makes it a thing with a past
            item_id = gear.materialize(world, me, "weapon")
        if not isinstance(item_id, int) or item_id not in world.targets(me, "owns"):
            return self._turn([("You have no such thing.", "system")])
        self.submenu = "gear"
        return self._turn(item_lines(world, me, world.entity(item_id)))

    def _do_buy_gear(self, key):
        world, me, here = self.world, self.player.id, self.place.id
        self.submenu = "smith"
        if (why := smithy.buy_block(world, me, here, key)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(smithy.buy_events(world, me, here, key)))

    def _do_sell_gear(self, item_id):
        world, me, here = self.world, self.player.id, self.place.id
        self.submenu = "smith"
        if (why := smithy.sell_block(world, me, here, item_id)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(smithy.sell_events(world, me, here, item_id)))

    def _do_draw_gear(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        faction, slot = target if isinstance(target, tuple) else (None, None)
        if faction is None or (why := armoury.draw_block(world, me, faction, slot, here)) is not None:
            return self._turn([(why if faction is not None else "There is no armoury here.", "system")])
        return self._turn(self._commit(armoury.draw_events(world, me, faction, slot, here)))

    def _do_return_gear(self, item_id):
        world, me, here = self.world, self.player.id, self.place.id
        item = world.entity(item_id) if isinstance(item_id, int) else None
        if item is None or item_id not in world.targets(me, "owns") or item.data.get("armoury") is None \
                or world.entity(item.data["armoury"]).data.get("seat") != here:
            return self._turn([("You cannot return that here.", "system")])
        return self._turn(self._commit(armoury.return_events(world, me, item_id, here)))

    def _do_return_heirloom(self, item_id):
        world, me, here = self.world, self.player.id, self.place.id
        if (why := FW.return_block(world, me, item_id, here)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(FW.return_events(world, me, item_id, here)))

    def _do_take_gear(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        loser, slot = target if isinstance(target, tuple) else (None, None)
        if loser is None or (why := spoils.take_block(world, me, loser, slot, here)) is not None:
            return self._turn([(why if loser is not None else "There is nothing to take.", "system")])
        return self._turn(self._commit(spoils.take_events(world, me, loser, slot, here)))

    def _do_take_lying(self, item_id):
        world, me, here = self.world, self.player.id, self.place.id
        if item_id not in FW.lying_at(world, here):
            return self._turn([("It is not here.", "system")])
        return self._turn(self._commit(FW.take_lying_events(world, me, item_id, here)))

    def _do_answer_demand(self, hand_over):
        if self._demand is None:
            return self._turn([("No one asks anything of you.", "system")])
        demander, item = self._demand
        self._demand = None
        if item not in self.world.targets(self.player.id, "owns"):
            return self._turn([("You no longer have it.", "system")])
        return self._turn(self._commit(provenance.demand_events(self.world, self.player.id, demander, item,
                                                                self.place.id, bool(hand_over))))

    def _do_answer_challenge(self, accept):
        if not accept and self._stake is not None and self._stake[0] == self.challenger:
            self._stake = None  # declined: they will not ask again while you stay
        return super()._do_answer_challenge(accept)

    def _do_duel_for_weapon(self, target):
        npc, item = target if isinstance(target, tuple) else (None, None)
        if npc is None or item not in self.world.targets(npc, "owns") or self.focus != npc:
            return self._turn([("They do not hold it.", "system")])
        return self._turn(self._start_duel(npc, "duel", purpose={"weapon": item}))
