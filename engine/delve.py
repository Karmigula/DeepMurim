"""The delve in the engine (phase 4f spec 3, 6): the gate's choices outside, and inside, a menu of the chamber."""

import systems.chambers as C
import systems.delve as D
import systems.delvers as R
import systems.secret_realms as SR
from world.events import commit
import systems.sky as sky
from engine.actions import Action, Choice
from narrate.realm_text import chamber_line
from systems.bodies import load_body
from systems.realms import MAX_REALM, REALMS, realm_title
from systems.time import format_date
from world.gen.materialize import people_at

INSIDE_VERBS = frozenset({
    "look", "journal", "help", "unknown", "ambiguous", "buy_token", "back", "more_menu", "people", "talk", "farewell", "ask",
    "ask_about", "news", "rumours", "tell_menu", "standing", "ledger", "lineage", "rankings", "tournaments", "realms",
    "intent", "flee", "yield_duel", "verdict", "use_menu", "use", "challenge", "spar",
    "delve_on", "delve_back", "leave_realm", "take_treasure", "delve_rest", "realms",
    "fight_guardian", "slip_past", "attempt_trial", "face_shade", "take_remains",
    "ask_pass", "fight_rival", "join_band",
    "sealed_cultivate", "search_exit", "heir_carry_on", "succeed", "new_world", "newcomer",
})
SEALED_VERBS = frozenset({
    "look", "journal", "help", "unknown", "ambiguous", "back", "more_menu", "standing", "ledger", "lineage", "rankings",
    "tournaments", "realms", "breakthrough", "sealed_cultivate", "search_exit", "heir_carry_on", "succeed",
    "new_world", "newcomer",
})
TRIAL_LABELS = {"formation": "Read the ancient array", "pressure": "Walk into the pressing qi",
                "mirror": "Face the bronze mirror"}


class DelveMixin:
    def _inside(self) -> dict | None:
        return D.position(self.world, self.player.id)

    # --- outside: the gate ---------------------------------------------------------------------
    def _general_extras(self) -> list:
        extras = super()._general_extras()
        world, me = self.world, self.player.id
        if self._inside():
            return extras
        for realm in D.realms_at(world, self.place.id):
            name = world.entity(realm).name
            days = D.days_left(world, D.gate_open(world, realm))
            why, how = D.entry(world, realm, me)
            extras.append(Choice(f"Enter {name} (the gate closes in {days} days)", Action("enter_realm", realm)))
            if why and how == "sneak":
                extras.append(Choice(f"Slip into {name} past the sects' guards", Action("sneak_realm", realm)))
        return extras

    def _do_enter_realm(self, realm):
        if realm is None:  # typed: the realm whose gate stands open here
            realm = next(iter(D.realms_at(self.world, self.place.id)), None)
        if realm is None:
            return self._turn([("No gate stands open here.", "system")])
        why, how = D.entry(self.world, realm, self.player.id)
        if why:
            return self._turn([(why, "system")])
        self._commit(D.enter_events(self.world, realm, self.player.id, how))
        seen = list(self.player.data.get("realms_seen", []))
        if realm not in seen:
            self.world.update_data(self.player.id, realms_seen=seen + [realm])
        return self._do_look(None)

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        token = D.token_offer(self.world, npc.id, self.player.id)
        if token is not None:
            price = D.TOKEN_PRICE * self.world.entity(token).data["value"]
            extras.append(Choice(f"Buy their jade token ({price} silver)", Action("buy_token", npc.id)))
        return extras

    def _do_buy_token(self, holder):
        events = D.buy_events(self.world, self.player.id, holder) if isinstance(holder, int) else []
        if not events:
            return self._turn([("You cannot buy that token.", "system")])
        return self._turn(self._commit(events))

    def _do_sneak_realm(self, realm):
        why, how = D.entry(self.world, realm, self.player.id) if isinstance(realm, int) else ("", "")
        if how != "sneak":
            return self._turn([("There is no slipping past anyone here.", "system")])
        lines = self._commit(D.sneak_events(self.world, realm, self.player.id))
        return self._do_look(None) if self._inside() else self._turn(lines)

    # --- inside ----------------------------------------------------------------------------------
    def _gate(self, action):
        if self.world.entity(self.player.id).data.get("sealed_in"):
            if action.verb not in SEALED_VERBS:
                return self._turn([("The gate is shut; there is only the realm, and waiting.", "system")])
            return super()._gate(action)
        if self._inside() and self.combat is None and not self.player.data.get("dying") \
                and action.verb not in INSIDE_VERBS:
            realm = self.world.entity(self._inside()["realm"])
            return self._turn([(f"You are inside {realm.name}; that must wait until you are out.", "system")])
        return super()._gate(action)

    def _before_scene(self) -> None:
        super()._before_scene()
        pos = self._inside()
        if pos:  # the gate's clock runs in the world outside
            sky.observe(self.world, self.world.entity(pos["realm"]).data["gate"])

    def _delve_lines(self) -> list:
        found = D.here(self.world, self.player.id)
        realm, floor, c, room = found
        floors = realm.data["floors"]
        occurrence = D.gate_open(self.world, realm.id)
        gate = f"the gate closes in {D.days_left(self.world, occurrence)} days" if occurrence else "the gate is shut"
        lines = [(f"{realm.name[0].upper()}{realm.name[1:]}, floor {floor} of {len(floors)}, "
                  f"chamber {c + 1} of {len(floors[floor - 1])} ({gate})", "heading"),
                 (chamber_line(self.world, realm, floor, c, room), "dim")]  # shown after every step: status, not prose
        others = [p.name for p in people_at(self.world, realm.id, exclude=self.player.id)
                  if (p.data.get("delve_at") or [None])[:2] == [floor, c]]  # placed by Task 5
        if others:
            lines.append(("Here: " + ", ".join(others) + ".", "dim"))
        near = [p for p in people_at(self.world, realm.id, exclude=self.player.id)
                if not p.data.get("realm_spirit") and (p.data.get("delve_at") or [None])[0] == floor
                and p.data["delve_at"][:2] != [floor, c]]
        if near:
            lines.append(("You hear others somewhere on this floor.", "dim"))
        return lines

    def _realm_news(self) -> list:
        """The heralds of an opening here, and its gate standing open: each stage told once (spec §6)."""
        import systems.secret_realms as SR
        from narrate.realm_text import stage_words
        world, town = self.world, self.place.id
        before = dict(self.player.data.get("realm_heralds", {}))
        told, lines, seen = dict(before), [], list(self.player.data.get("realms_seen", []))
        for realm in SR.realms(world):
            occurrence = SR.opening_of(world, realm)
            if occurrence is None or world.entity(realm).data["gate"] != town:
                continue
            stage = SR.stage_of(world, occurrence)
            if stage in ("foretold", "announced", "active") and told.get(str(occurrence)) != stage:
                told[str(occurrence)] = stage
                lines.append((stage_words(world, world.entity(occurrence), stage), "dim"))
            if stage == "active" and realm not in seen:
                seen.append(realm)  # you have seen its gate: it is on your page now
        live = {str(SR.opening_of(world, r)) for r in SR.realms(world)}
        told = {k: v for k, v in told.items() if k in live}
        if told != before or seen != list(self.player.data.get("realms_seen", [])):
            world.update_data(self.player.id, realm_heralds=told, realms_seen=seen)
        return lines

    def _after_arrival(self) -> list:
        return super()._after_arrival() + ([] if self._inside() else self._realm_news())

    def _after_look(self) -> list:
        return super()._after_look() + ([] if self._inside() else self._realm_news())

    def _do_realms(self, _target):
        from engine.realm_page import realms_lines
        return self._turn(realms_lines(self.world, self.player.id))

    def _special_look(self):
        if not self._inside():  # outside, or the gate closed on the scene (Task 6)
            return super()._special_look()
        return self._delve_lines()

    def _chamber_choices(self, realm, floor: int, c: int, room: dict) -> list:
        world, me = self.world, self.player.id
        out = []
        if room["kind"] == "treasure" and room["state"] == "untouched":
            out.append(Choice(f"Take {chamber_prize(room)}", Action("take_treasure")))
        if room["kind"] == "guardian" and room["state"] == "untouched":
            species = room["contents"]["species"]
            out += [Choice(f"Fight the {species}", Action("fight_guardian")),
                    Choice(f"Slip past the {species}", Action("slip_past"))]
        if C.trial_open(world, me):
            out.append(Choice(TRIAL_LABELS[room["contents"]["trial"]], Action("attempt_trial")))
        if C.inheritance_open(world, me):
            out.append(Choice(f"Kneel before {realm.data['master']['name']}", Action("face_shade")))
        occurrence = SR.opening_of(world, realm.id)  # at any stage: the gate may have shut this very step
        for i in R.here(world, me):
            team = world.entity(occurrence).data["data"]["teams"][i]
            head = world.entity(R.leader(world, team))
            if me not in team.get("let_pass", []) and team.get("with") != me:
                out += [Choice(f"Ask {head.name} to let you pass", Action("ask_pass", i)),
                        Choice(f"Fight {head.name}", Action("fight_rival", i))]
            if team.get("with") is None and R.join_events(world, me, i):
                out.append(Choice(f"Travel with {head.name}'s band for a floor", Action("join_band", i)))
            out.append(Choice(f"Talk to {head.name}", Action("talk", head.id)))
        for item in room["contents"].get("remains", []):
            out.append(Choice(f"Take {world.entity(item).name} from the fallen", Action("take_remains", item)))
        return out

    def _special_choices(self):
        pos = self._inside()
        if not pos or self.combat is not None or self.encounter is not None or self.challenger is not None \
                or self.focus is not None or self.player.data.get("dying"):
            return super()._special_choices()
        realm, floor, c, room = D.here(self.world, self.player.id)
        choices = self._chamber_choices(realm, floor, c, room)
        can = D.moves(self.world, self.player.id)
        floors = realm.data["floors"]
        if can.get("on"):
            down = room["kind"] == "stair" and c == len(floors[floor - 1]) - 1
            choices.append(Choice("Take the stair down" if down else "Go on to the next chamber", Action("delve_on")))
        if can.get("back"):
            choices.append(Choice("Go back" if c > 0 else "Climb back up the stair", Action("delve_back")))
        if can.get("leave"):
            choices.append(Choice("Leave the realm", Action("leave_realm")))
        choices.append(Choice("Catch your breath (a watch)", Action("delve_rest")))
        choices += [Choice("Look around", Action("look")), Choice("Read your journal", Action("journal"))]
        return choices[:9], choices[9:]

    def _special_status(self):
        pos = self._inside()
        if not pos:
            return super()._special_status()
        realm = self.world.entity(pos["realm"])
        return f"{self.player.name} | {realm_title(self.body())} | {format_date(self.world.time)} | {realm.name}, floor {pos['floor']}"

    def _special_art(self):
        pos = self._inside()
        if not pos or self.focus is not None:
            return super()._special_art()
        gate = self.world.entity(self.world.entity(pos["realm"]).data["gate"])
        return {"type": "scene", "terrain": gate.data["terrain"], "settlement": gate.data["kind"],
                "watch": self.world.time % 4, "hall": None}

    def _step(self, events: list, refusal: str):
        if not events:
            return self._turn([(refusal, "system")])
        lines = self._commit(events)
        if self._inside():  # a band sharing your chamber may strike first; then every band takes its step (Task 5)
            foe = R.ambusher(self.world, self.player.id)
            if foe is not None:
                lines.append((f"{self.world.entity(foe).name} strikes without a word!", "red"))
                return self._turn(lines + self._start_duel(foe, "duel", purpose={"rival": R.here(self.world, self.player.id)[0]}))
            stepped = R.step_events(self.world, self.player.id)
            if stepped:
                commit(self.world, stepped)  # the world's events, not the player's: nothing to narrate
            sky.observe(self.world, self.world.entity(self._inside()["realm"]).data["gate"])  # the gate may close now
            if self.world.entity(self.player.id).data.get("sealed_in"):
                return self._turn(lines + (self._special_look() or []))
        return self._turn(lines + (self._delve_lines() if self._inside() else []))

    def _do_delve_on(self, _target):
        return self._step(D.move_events(self.world, self.player.id, "on"), "The way on is barred.")

    def _do_delve_back(self, _target):
        return self._step(D.move_events(self.world, self.player.id, "back"), "There is no way back from here.")

    def _do_take_treasure(self, _target):
        return self._step(D.take_events(self.world, self.player.id), "There is nothing here to take.")

    def _do_delve_rest(self, _target):
        return self._step(D.rest_events(self.world, self.player.id), "You are not inside a realm.")

    def _do_leave_realm(self, _target):
        events = D.leave_events(self.world, self.player.id)
        if not events:
            return self._turn([("You can only leave from the first floor.", "system")])
        self._commit(events)
        return self._do_look(None)


def chamber_prize(room: dict) -> str:
    prize = room["contents"]["prize"]
    return prize.get("name") or {"manual": "a martial manual", "star_iron": "a lump of star iron"}.get(prize["kind"], "the treasure")



def _room(game):
    return D.here(game.world, game.player.id)


class ChamberMixin:
    """The chambers' verbs (Task 4): a Game base beside DelveMixin, whose steps and lines it uses."""

    def _do_fight_guardian(self, _target):
        found = _room(self)
        if found is None or found[3]["kind"] != "guardian" or found[3]["state"] != "untouched":
            return self._turn([("Nothing here bars your way.", "system")])
        realm, floor, c, room = found
        foe = C.guardian(self.world, realm.id, floor, c)
        return self._turn(self._start_duel(foe, "duel", purpose={"guardian": [realm.id, floor, c]}))

    def _do_slip_past(self, _target):
        found = _room(self)
        if found is None or found[3]["kind"] != "guardian" or found[3]["state"] != "untouched":
            return self._turn([("Nothing here bars your way.", "system")])
        realm, floor, c, room = found
        lines = self._commit(C.slip_events(self.world, self.player.id))
        if self.world.entity(realm.id).data["floors"][floor - 1][c]["state"] == "passed":
            return self._turn(lines + self._delve_lines())
        foe = C.guardian(self.world, realm.id, floor, c)  # seen: it turns on you
        return self._turn(lines + self._start_duel(foe, "duel", purpose={"guardian": [realm.id, floor, c]}))

    def _do_attempt_trial(self, _target):
        if _room(self) is None or not C.trial_open(self.world, self.player.id):
            return self._turn([("There is no trial for you here.", "system")])
        realm, floor, c, room = _room(self)
        if room["contents"]["trial"] == "mirror":
            foe = C.mirror(self.world, realm.id, floor, c, self.player.id)
            return self._turn(self._start_duel(foe, "spar", purpose={"mirror": [realm.id, floor, c]}))
        return self._step(C.trial_events(self.world, self.player.id), "There is no trial for you here.")

    def _do_face_shade(self, _target):
        if _room(self) is None or not C.inheritance_open(self.world, self.player.id):
            return self._turn([("No one waits for you here.", "system")])
        realm = _room(self)[0]
        foe = C.shade(self.world, realm.id, self.player.id)
        return self._turn(self._start_duel(foe, "test", purpose={"inheritance": realm.id}))

    def _do_take_remains(self, item):
        return self._step(C.remains_events(self.world, self.player.id, item) if isinstance(item, int) else [],
                          "There is nothing like that here.")

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        purpose = data.get("purpose") or {}
        me = self.player.id
        if "guardian" in purpose and data.get("result") == "won":
            lines += self._commit(C.slain_events(self.world, me, purpose))
        elif "mirror" in purpose:
            lines += self._commit(C.mirror_events(self.world, me, purpose, data.get("result") == "spar_won"))
        elif "inheritance" in purpose:
            lines += self._commit(C.shade_events(self.world, me, purpose, data.get("result") == "passed"))
        return lines




class RivalMixin:
    """The bands' verbs (Task 5): a Game base beside DelveMixin."""

    def _band(self, i):
        return isinstance(i, int) and i in R.here(self.world, self.player.id)

    def _do_ask_pass(self, i):
        if not self._band(i):
            return self._turn([("No band stands here.", "system")])
        lines = self._commit(R.pass_events(self.world, self.player.id, i))
        if R.blocking(self.world, self.player.id):
            foe = R.ambusher(self.world, self.player.id)
            if foe is not None:
                return self._turn(lines + self._start_duel(foe, "duel", purpose={"rival": i}))
        return self._turn(lines + self._delve_lines())

    def _do_fight_rival(self, i):
        if not self._band(i):
            return self._turn([("No band stands here.", "system")])
        occurrence = SR.opening_of(self.world, self._inside()["realm"])
        head = R.leader(self.world, self.world.entity(occurrence).data["data"]["teams"][i])
        return self._turn(self._start_duel(head, "duel", purpose={"rival": i}))

    def _do_join_band(self, i):
        events = R.join_events(self.world, self.player.id, i) if self._band(i) else []
        if not events:
            return self._turn([("They will not have you along.", "system")])
        return self._turn(self._commit(events) + self._delve_lines())

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        purpose = data.get("purpose") or {}
        if "rival" in purpose and data.get("result") == "won" and self._inside() \
                and purpose["rival"] in R.here(self.world, self.player.id):
            lines += self._commit(R.rout_events(self.world, self.player.id, purpose["rival"]))
        return lines



class SealedMixin:
    """The sealed player's choices (Task 6): a Game base beside DelveMixin."""

    def _special_choices(self):
        import systems.sealed as S
        realm = S.sealed_realm(self.world, self.player.id)
        if realm is None or self.combat is not None or self.focus is not None or self.player.data.get("dying"):
            return super()._special_choices()
        choices = []
        if self.world.entity(realm).data["period"] is not None:
            choices.append(Choice("Cultivate a season in the dense qi", Action("sealed_cultivate")))
        body = load_body(self.world, self.player.id)
        if body.bottleneck and body.realm < MAX_REALM:  # years of dense qi reach a bottleneck (4f final review)
            choices.append(Choice(f"Attempt breakthrough to {REALMS[body.realm + 1].name}", Action("breakthrough")))
        choices += [Choice("Search the sealed floors for another way out (a season)", Action("search_exit")),
                    Choice("Let your heir carry on", Action("heir_carry_on")),
                    Choice("Look around", Action("look")), Choice("Read your journal", Action("journal"))]
        return choices, []

    def _special_look(self):
        import systems.sealed as S
        realm = S.sealed_realm(self.world, self.player.id)
        if realm is None:
            return super()._special_look()
        entity = self.world.entity(realm)
        when = "It will open again when its season comes round." if entity.data["period"] is not None \
            else "It will not open again."
        return [(f"You are sealed in {entity.name}. {when}", "heading")]

    def _do_sealed_cultivate(self, _target):
        import systems.sealed as S
        events = S.season_events(self.world, self.player.id)
        if not events:
            return self._turn([("There is no waiting this out.", "system")])
        lines = self._commit(events)
        return self._turn(lines + (self._special_look() or []))

    def _do_search_exit(self, _target):
        import systems.sealed as S
        events = S.search_events(self.world, self.player.id)
        if not events:
            return self._turn([("You are not sealed in anywhere.", "system")])
        self._commit(events)
        return self._do_look(None)

    def _do_heir_carry_on(self, _target):
        import systems.sealed as S
        events = S.lost_events(self.world, self.player.id)
        if not events:
            return self._turn([("You are not sealed in anywhere.", "system")])
        self._commit(events)
        return self._do_look(None)
