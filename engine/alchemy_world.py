"""The alchemy world in the engine (phase 5c spec 7): a sect's pill hall and garden, the Guild, the clinic and the
famous doctors, theft by night, healing, poison for hire, and control pills from all three sides."""

import systems.control as C
import systems.duties as duties
import systems.encounters as encounters
import systems.guild as G
import systems.hall_theft as T
import systems.npc_alchemy as N
import systems.physic as PY
import systems.pill_hall as PH
import systems.recipe_trade as RT
from engine.actions import Action, Choice
from engine.alchemy_world_page import clinic_lines, guild_lines, hall_lines, night_lines, recipe_label, scroll_lines
from systems import factions as F
from systems import halls
from systems.bodies import load_body

WORLD_MENUS = ("pill_hall", "guild", "clinic", "night", "bound")
TALK_MENU = "remedies"
STEAL_WORDS = {"garden": "herbs from the {name}'s garden", "hall": "pills from the {name}'s pill hall",
               "scroll": "a secret scroll from the {name}'s pill hall"}


class AlchemyWorldMixin:
    # --- where things are -------------------------------------------------------------------------------------
    def _seats_here(self) -> list[int]:
        return [f for f in self.world.entity(self.place.id).data.get("seats", [])
                if not self.world.entity(f).data.get("dissolved")]

    def _my_halls(self) -> list[int]:
        """Sects seated here whose hall or garden the player may use: their own."""
        me = self.player.id
        return [f for f in self._seats_here() if (PH.keeps_hall(self.world, f) or PH.keeps_garden(self.world, f))
                and (F.membership(self.world, me, f) or (0, {}))[1].get("status") == "member"]

    def _robbable(self) -> list[int]:
        return [f for f in self._seats_here() if PH.keeps_hall(self.world, f) or PH.keeps_garden(self.world, f)]

    # --- choices -----------------------------------------------------------------------------------------------
    def _general_extras(self) -> list:
        extras = super()._general_extras()
        world, me, here = self.world, self.player.id, self.place.id
        if self.world.entity(here).kind != "town":
            return extras
        if self._my_halls():
            extras.append(Choice("Your sect's pill hall and garden", Action("pill_hall")))
        if G.branch_here(world, here):
            extras.append(Choice("The Alchemists' Guild", Action("guild")))
        extras.append(Choice("Visit the physician", Action("clinic")))
        if self._robbable():
            extras.append(Choice("Around the halls by night...", Action("night")))
        if C.servants_of(world, me):
            extras.append(Choice("Those bound to you...", Action("bound_menu")))
        if C.force_block(world, me) is None:
            extras.append(Choice("Force the worms out with your qi", Action("force_worms")))
        beaten = getattr(self, "_beaten", None)
        if beaten is not None and C.force_feed_block(world, me, beaten, here) is None:
            extras.append(Choice(f"Force a control pill on {world.entity(beaten).name}", Action("force_control", beaten)))
        return extras

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        if self._remedies(npc):
            extras.append(Choice("Alchemy and medicine...", Action("remedies")))
        return extras

    def _remedies(self, npc) -> list:
        """What the player can do with this person, alchemy-wise (the talk submenu)."""
        world, me, here = self.world, self.player.id, self.place.id
        out = []
        if PY.heal_block(world, me, npc.id, here) is None:
            out.append(Choice(f"Offer to treat {npc.name}", Action("heal", npc.id)))
        if npc.data.get("doctor"):
            for what in PY.doctor_cures(world, me):
                out.append(Choice(f"Ask them to cure your {what}", Action("doctor_cure", (npc.id, what))))
            if npc.data["doctor"]["whim"] == "eccentric" and npc.id not in (world.entity(me).data.get("go_won") or []):
                out.append(Choice("Play them at go", Action("play_go", npc.id)))
        if G.is_alchemist(world, npc.id):
            for key in RT.teach_offers(world, me, npc.id):
                if RT.teach_block(world, me, npc.id, key) is None:
                    out.append(Choice(f"Learn their {recipe_label(world, key)} ({RT.price(key)} silver)",
                                      Action("learn_recipe", (npc.id, key))))
            for grade in N.stall_offers(world, npc.id):
                out.append(Choice(f"Buy a grade-{grade} pill ({N.stall_price(grade)} silver)",
                                  Action("buy_npc_pill", (npc.id, grade))))
        offer = PY.contract_offer(world, npc.id, me)
        if offer is not None:
            out.append(Choice(f"Take their silver to poison {world.entity(offer['target']).name} ({offer['silver']})",
                              Action("take_contract", npc.id)))
        if PY.contract_poison_block(world, me, npc.id, here) is None:
            out.append(Choice(f"Slip poison into {npc.name}'s cup", Action("contract_poison", npc.id)))
        if PY.fee_block(world, me, npc.id) is None:
            out.append(Choice("Claim your fee for the poisoning", Action("claim_fee", npc.id)))
        if C.free_block(world, me, npc.id, here) is None:
            out.append(Choice(f"Kill the worms in {npc.name} with your antidote", Action("free_bound", npc.id)))
        for fid, _, d in F.memberships(world, npc.id):
            if d.get("role") != "keeper" or d.get("status", "member") != "member":
                continue
            for scroll in RT.scrolls_of(world, me):
                if RT.secret_sale_block(world, me, scroll.id, fid, here) is None:
                    sect = world.entity(scroll.data["faction"]).name
                    price = RT.price(scroll.data["key"]) * RT.RIVAL_SHARE
                    out.append(Choice(f"Sell them the {sect}'s secret ({price} silver)",
                                      Action("sell_secret", (npc.id, scroll.id, fid))))
        return out

    def _faction_options(self, npc) -> list:
        options = super()._faction_options(npc)
        world, me, here = self.world, self.player.id, self.place.id
        if duties.open_duty(world, me) is not None:
            return options
        for fid in halls.recruits_for(world, npc.id):
            found = F.membership(world, me, fid)
            if found and found[1].get("status", "member") == "member" and halls.keeper_at(world, fid, here) == npc.id \
                    and PH.keeps_hall(world, fid) and world.entity(fid).data.get("seat") == here:
                options.append(Choice("Ask for an alchemy duty", Action("alchemy_duty", fid)))
        return options

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        world, me, here = self.world, self.player.id, self.place.id
        if self.focus is not None:
            if self.submenu == TALK_MENU:
                options[TALK_MENU] = (self._remedies(world.entity(self.focus)), Action("talk_menu"))
            return options
        if self.submenu == "alchemy" and "alchemy" in options:  # scrolls are read from the alchemy page
            choices, back = options["alchemy"]
            reads = [Choice(f"Read {s.name}", Action("read_scroll", s.id)) for s in RT.scrolls_of(world, me)
                     if RT.read_block(world, me, s.id) is None]
            options["alchemy"] = (reads + choices, back)
        if self.submenu not in WORLD_MENUS:
            return options
        choices = []
        if self.submenu == "pill_hall":
            for fid in self._my_halls():
                name = world.entity(fid).name
                for grade, kind in PH.offers(world, me, fid):
                    cost = PH.cost(world, fid, grade)
                    choices.append(Choice(f"Draw a grade-{grade} {kind} pill from the {name} ({cost} merit)",
                                          Action("draw_pill", (fid, grade, kind))))
                for herb, (count, grade) in sorted(PH.garden(world, fid).items()):
                    if count > 0 and PH.harvest_block(world, me, fid, herb, here) is None:
                        choices.append(Choice(f"Harvest {herb} from the {name}'s garden "
                                              f"({PH.harvest_cost(world, fid, grade)} merit)", Action("harvest", (fid, herb))))
                if not PH.own(world, fid):
                    for key in RT.secret_recipes(world, fid):
                        if RT.secret_block(world, me, fid, key, here) is None:
                            choices.append(Choice(f"Ask for the {name}'s secret scroll ({RT.secret_cost(key)} merit)",
                                                  Action("secret_scroll", (fid, key))))
        elif self.submenu == "guild":
            if G.join_block(world, me, here) is None:
                choices.append(Choice("Join the Guild", Action("guild_join")))
            if G.exam_block(world, me, here) is None:
                rank = world.entity(me).data["guild_rank"] + 1
                choices.append(Choice(f"Sit the examination for the {G.ORDINALS[rank]} rank "
                                      f"({G.EXAM_FEE * rank} silver)", Action("guild_exam")))
            for key in RT.guild_offers(world, me):
                if RT.buy_block(world, me, key, here) is None:
                    choices.append(Choice(f"Buy a scroll of {recipe_label(world, key)} ({RT.price(key)} silver)",
                                          Action("buy_scroll", key)))
            for scroll in RT.scrolls_of(world, me):
                choices.append(Choice(f"Sell {scroll.name} ({RT.sell_price(world, scroll.id)} silver)",
                                      Action("sell_scroll", scroll.id)))
        elif self.submenu == "clinic":
            for injury in PY.treatable(load_body(world, me), world.time):
                choices.append(Choice(f"Have your {injury.location} treated ({PY.treat_price(injury.severity)} silver)",
                                      Action("physician_treat", injury.id)))
            if PY.cure_block(world, me, here) is None:
                grade = PY.curable(load_body(world, me))
                choices.append(Choice(f"Have your poison cured ({PY.cure_price(grade)} silver)", Action("physician_cure")))
            if PY.read_block(world, me, here) is None and load_body(world, me).poisons:
                choices.append(Choice(f"Have your body read ({PY.READ_PRICE} silver)", Action("read_body")))
            choices.append(Choice("Ask after famous doctors", Action("ask_doctor")))
        elif self.submenu == "night":
            if not T.night(world):
                choices.append(Choice("Wait for nightfall", Action("nightfall")))
            for fid in self._robbable():
                name = world.entity(fid).name
                if T.look_block(world, me, fid, here) is None:
                    choices.append(Choice(f"Look over the {name}'s hall and garden", Action("survey", fid)))
                for target, words in STEAL_WORDS.items():
                    why = T.steal_block(world, me, fid, target, here)
                    if why is None or why == "Something guards the garden.":
                        choices.append(Choice(f"Steal {words.format(name=name)}", Action("steal", (fid, target))))
        elif self.submenu == "bound":
            for servant in C.servants_of(world, me):
                if C.feed_block(world, me, servant) is None:
                    choices.append(Choice(f"Send {world.entity(servant).name} the month's antidote",
                                          Action("feed_servant", servant)))
        options[self.submenu] = (choices, Action("back"))
        return options

    # --- the world around ---------------------------------------------------------------------------------------
    def _after_arrival(self) -> list:
        lines = super()._after_arrival()
        world, me, here = self.world, self.player.id, self.place.id
        if world.entity(here).kind == "town":
            brought = PY.patient_events(world, me, here)
            if brought:
                lines += self._commit(brought)
        return lines

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        entry = self.world.chronicle_entry(data["duel"]) if data.get("duel") else None
        bound = C.bound(self.world, self.player.id)
        if entry is not None and bound and bound["since"] >= entry.time and bound["master"] == entry.actors[1]:
            lines.append((f"You wake with a bitter taste. {self.world.entity(entry.actors[1]).name} has fed you "
                          "a control pill: serve, or the worms wake.", "red"))
        return lines

    def _after_turn(self, turn):
        """After the whole deed: the worms of an unfed control pill, the month's service, a void contract."""
        turn = super()._after_turn(turn)
        world, me = self.world, self.player.id
        if self.player.data.get("dying") or self.player.data.get("dead"):
            return turn
        lines = []
        if C.bound(world, me):
            if C.service_done(world, me):
                lines += self._commit(C.served_events(world, me, self.place.id))
            C.starve(world, me)
            deaths = C.death_events(world, me)
            if deaths:
                return self._turn(list(turn.lines) + self._commit(deaths) + self._death_lines())
        if PY.contract_lapsed(world, me):
            lines += self._commit(PY.void_events(world, me, self.place.id))
        return self._turn(list(turn.lines) + lines) if lines else turn

    # --- handlers: the sect's hall and garden -----------------------------------------------------------------------
    def _do_pill_hall(self, _target):
        self.submenu = "pill_hall"
        lines = []
        for fid in self._my_halls():
            lines += hall_lines(self.world, self.player.id, fid)
        return self._turn(lines or [("You belong to no sect that keeps a hall here.", "system")])

    def _do_draw_pill(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        faction, grade, kind = target if isinstance(target, tuple) and len(target) == 3 else (None, 0, "")
        self.submenu = "pill_hall"
        if faction is None or (why := PH.draw_block(world, me, faction, grade, kind, here)) is not None:
            return self._turn([(why if faction is not None else "There is no such pill.", "system")])
        return self._turn(self._commit(PH.draw_events(world, me, faction, grade, kind, here)))

    def _do_harvest(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        faction, herb = target if isinstance(target, tuple) and len(target) == 2 else (None, None)
        self.submenu = "pill_hall"
        if faction is None or (why := PH.harvest_block(world, me, faction, herb, here)) is not None:
            return self._turn([(why if faction is not None else "Nothing like that grows here.", "system")])
        return self._turn(self._commit(PH.harvest_events(world, me, faction, herb, here)))

    def _do_secret_scroll(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        faction, key = target if isinstance(target, tuple) and len(target) == 2 else (None, None)
        self.submenu = "pill_hall"
        if faction is None or (why := RT.secret_block(world, me, faction, key, here)) is not None:
            return self._turn([(why if faction is not None else "The hall keeps no such scroll.", "system")])
        return self._turn(self._commit(RT.secret_events(world, me, faction, key, here)))

    # --- handlers: the Guild and scrolls ----------------------------------------------------------------------------
    def _do_guild(self, _target):
        if not G.branch_here(self.world, self.place.id):
            return self._turn([("The Guild keeps its branches in the cities.", "system")])
        self.submenu = "guild"
        return self._turn(guild_lines(self.world, self.player.id))

    def _do_guild_join(self, _target):
        world, me, here = self.world, self.player.id, self.place.id
        self.submenu = "guild"
        if (why := G.join_block(world, me, here)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(G.join_events(world, me, here)))

    def _do_guild_exam(self, _target):
        world, me, here = self.world, self.player.id, self.place.id
        self.submenu = "guild"
        if (why := G.exam_block(world, me, here)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(G.exam_events(world, me, here)))

    def _do_buy_scroll(self, key):
        world, me, here = self.world, self.player.id, self.place.id
        self.submenu = "guild"
        if not isinstance(key, str) or (why := RT.buy_block(world, me, key, here)) is not None:
            return self._turn([(why if isinstance(key, str) else "The Guild sells no such scroll.", "system")])
        return self._turn(self._commit(RT.buy_events(world, me, key, here)))

    def _do_sell_scroll(self, item):
        world, me, here = self.world, self.player.id, self.place.id
        self.submenu = "guild"
        if (why := RT.sell_block(world, me, item, here)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(RT.sell_events(world, me, item, here)))

    def _do_read_scroll(self, item):
        world, me = self.world, self.player.id
        if item is None:  # typed: the first scroll one has not yet learnt
            item = next((s.id for s in RT.scrolls_of(world, me) if RT.read_block(world, me, s.id) is None), None)
        self.submenu = "alchemy"
        if item is None or (why := RT.read_block(world, me, item)) is not None:
            return self._turn([(why if item is not None else "You have no scroll to read.", "system")])
        return self._turn(self._commit(RT.read_events(world, me, item, self.place.id)))

    def _do_alchemy(self, target):
        turn = super()._do_alchemy(target)
        turn.lines += scroll_lines(self.world, self.player.id)
        return turn

    # --- handlers: the clinic and the doctors -------------------------------------------------------------------------
    def _do_clinic(self, _target):
        if (why := PY.clinic_block(self.world, self.place.id)) is not None:
            return self._turn([(why, "system")])
        self.submenu = "clinic"
        return self._turn(clinic_lines(self.world, self.player.id, self.place.id))

    def _clinic_deed(self, why, events):
        self.submenu = "clinic"
        if why is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(events()))

    def _do_physician_treat(self, injury):
        world, me, here = self.world, self.player.id, self.place.id
        return self._clinic_deed(PY.treat_block(world, me, injury, here),
                                 lambda: PY.treat_events(world, me, injury, here))

    def _do_physician_cure(self, _target):
        world, me, here = self.world, self.player.id, self.place.id
        return self._clinic_deed(PY.cure_block(world, me, here), lambda: PY.cure_events(world, me, here))

    def _do_read_body(self, _target):
        world, me, here = self.world, self.player.id, self.place.id
        return self._clinic_deed(PY.read_block(world, me, here), lambda: PY.read_events(world, me, here))

    def _do_ask_doctor(self, _target):
        world, me, here = self.world, self.player.id, self.place.id
        return self._clinic_deed(PY.clinic_block(world, here), lambda: PY.ask_events(world, me, here))

    # --- handlers: by night --------------------------------------------------------------------------------------------
    def _do_night(self, _target):
        if not self._robbable():
            return self._turn([("No sect keeps a hall here.", "system")])
        self.submenu = "night"
        return self._turn(night_lines(self.world, self.player.id, self._robbable()))

    def _do_nightfall(self, _target):
        self.submenu = "night"
        if T.night(self.world):
            return self._turn([("It is dark already.", "system")])
        return self._turn(self._commit(T.nightfall_events(self.world, self.player.id, self.place.id)))

    def _do_survey(self, faction):
        world, me, here = self.world, self.player.id, self.place.id
        self.submenu = "night"
        if faction not in self._robbable() or (why := T.look_block(world, me, faction, here)) is not None:
            return self._turn([(why if faction in self._robbable() else "There is nothing to look at.", "system")])
        lines = self._commit(T.look_events(world, me, faction, here))
        return self._turn(lines + hall_lines(world, me, faction))

    def _do_steal(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        faction, what = target if isinstance(target, tuple) and len(target) == 2 else (None, None)
        if faction not in self._robbable():
            return self._turn([("There is nothing of theirs to take here.", "system")])
        why = T.steal_block(world, me, faction, what, here)
        if why == "Something guards the garden.":  # the guardian comes out of the dark (spec 2.4)
            met = T.guardian_events(world, me, faction, here)
            lines = self._commit(met)
            self.encounter = encounters.encounter_state(met[0])
            return self._turn(lines)
        self.submenu = "night"
        if why is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(T.steal_events(world, me, faction, what, here)))

    # --- handlers: in conversation -------------------------------------------------------------------------------------
    def _do_remedies(self, _target):
        if self.focus is None or not self._remedies(self.world.entity(self.focus)):
            return self._turn([("There is nothing of that kind to do with them.", "system")])
        self.submenu = TALK_MENU
        npc = self.world.entity(self.focus)
        rank = G.rank_of(self.world, npc.id) if G.is_alchemist(self.world, npc.id) else None
        told = [(f"{npc.name} is {G.title(rank)}.", "dim")] if rank else []  # their rank, told when you talk shop
        return self._turn(told + [("What will you do?", "system")])

    def _talk_deed(self, npc, why, events):
        if self.focus != npc:
            return self._turn([("They are not the one you are speaking with.", "system")])
        if why is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(events()))

    def _do_heal(self, npc):
        world, me, here = self.world, self.player.id, self.place.id
        return self._talk_deed(npc, PY.heal_block(world, me, npc, here), lambda: PY.heal_events(world, me, npc, here))

    def _do_doctor_cure(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        doctor, what = target if isinstance(target, tuple) and len(target) == 2 else (None, None)
        if doctor is None or not world.entity(doctor).data.get("doctor") or what not in PY.doctor_cures(world, me):
            return self._turn([("They cannot help you with that.", "system")])
        return self._talk_deed(doctor, PY.terms_block(world, me, doctor, here),
                               lambda: PY.doctor_events(world, me, doctor, what, here))

    def _do_play_go(self, doctor):
        world, me, here = self.world, self.player.id, self.place.id
        if doctor is None or not world.entity(doctor).data.get("doctor"):
            return self._turn([("They do not play.", "system")])
        return self._talk_deed(doctor, None, lambda: PY.go_events(world, me, doctor, here))

    def _do_learn_recipe(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        npc, key = target if isinstance(target, tuple) and len(target) == 2 else (None, None)
        return self._talk_deed(npc, RT.teach_block(world, me, npc, key) if npc else "They teach nothing.",
                               lambda: RT.teach_events(world, me, npc, key, here))

    def _do_buy_npc_pill(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        npc, grade = target if isinstance(target, tuple) and len(target) == 2 else (None, 0)
        return self._talk_deed(npc, N.stall_block(world, me, npc, grade) if npc else "They sell no pills.",
                               lambda: N.stall_events(world, me, npc, grade, here))

    def _do_take_contract(self, npc):
        world, me, here = self.world, self.player.id, self.place.id
        offer = PY.contract_offer(world, npc, me) if npc is not None else None
        return self._talk_deed(npc, None if offer else "They offer you nothing.",
                               lambda: PY.contract_events(world, me, offer, here))

    def _do_contract_poison(self, npc):
        world, me, here = self.world, self.player.id, self.place.id
        return self._talk_deed(npc, PY.contract_poison_block(world, me, npc, here),
                               lambda: PY.contract_poison_events(world, me, npc, here))

    def _do_claim_fee(self, npc):
        world, me, here = self.world, self.player.id, self.place.id
        return self._talk_deed(npc, PY.fee_block(world, me, npc), lambda: PY.fee_events(world, me, npc, here))

    def _do_free_bound(self, npc):
        world, me, here = self.world, self.player.id, self.place.id
        return self._talk_deed(npc, C.free_block(world, me, npc, here), lambda: C.free_events(world, me, npc, here))

    def _do_sell_secret(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        npc, item, buyer = target if isinstance(target, tuple) and len(target) == 3 else (None, None, None)
        return self._talk_deed(npc, RT.secret_sale_block(world, me, item, buyer, here) if npc else "They buy nothing.",
                               lambda: RT.secret_sale_events(world, me, item, buyer, here))

    def _do_alchemy_duty(self, faction):
        world, me, here = self.world, self.player.id, self.place.id
        if self.focus is None or halls.keeper_at(world, faction, here) != self.focus or not PH.keeps_hall(world, faction):
            return self._turn([("Only the keeper of a pill hall gives alchemy duties.", "system")])
        if duties.open_duty(world, me) is not None:
            return self._turn([("Finish your current duty first.", "system")])
        self.submenu = None
        return self._turn(self._commit(duties.issue_events(world, me, faction, self.focus, here, kind="alchemy")))

    # --- handlers: control pills ---------------------------------------------------------------------------------------
    def _do_force_control(self, npc):
        world, me, here = self.world, self.player.id, self.place.id
        if not isinstance(npc, int) or (why := C.force_feed_block(world, me, npc, here)) is not None:
            return self._turn([(why if isinstance(npc, int) else "There is no one to bind.", "system")])
        return self._turn(self._commit(C.force_feed_events(world, me, npc, here)))

    def _do_bound_menu(self, _target):
        world, me = self.world, self.player.id
        servants = C.servants_of(world, me)
        if not servants:
            return self._turn([("No one is bound to you.", "system")])
        self.submenu = "bound"
        lines = [("Bound to you by the worms:", "heading")]
        for servant in servants:
            days = max(0, round((C.bound(world, servant)["fed_until"] - world.time) / 4))
            lines.append((f"  {world.entity(servant).name}: fed for {days} more day(s)", "dim"))
        return self._turn(lines)

    def _do_feed_servant(self, npc):
        world, me, here = self.world, self.player.id, self.place.id
        self.submenu = "bound"
        if not isinstance(npc, int) or (why := C.feed_block(world, me, npc)) is not None:
            return self._turn([(why if isinstance(npc, int) else "No one is bound to you.", "system")])
        return self._turn(self._commit(C.feed_events(world, me, npc, here)))

    def _do_force_worms(self, _target):
        world, me, here = self.world, self.player.id, self.place.id
        if (why := C.force_block(world, me)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(C.force_events(world, me, here)))
