"""The delve in the engine (phase 4f spec 3, 6): the gate's choices outside, and inside, a menu of the chamber."""

import systems.chambers as C
import systems.delve as D
import systems.sky as sky
from engine.actions import Action, Choice
from narrate.realm_text import chamber_line
from systems.realms import realm_title
from systems.time import format_date
from world.gen.materialize import people_at

INSIDE_VERBS = frozenset({
    "look", "journal", "help", "unknown", "ambiguous", "buy_token", "back", "more_menu", "people", "talk", "farewell", "ask",
    "ask_about", "news", "rumours", "tell_menu", "standing", "ledger", "lineage", "rankings", "tournaments", "realms",
    "intent", "flee", "yield_duel", "verdict", "use_menu", "use", "challenge", "spar",
    "delve_on", "delve_back", "leave_realm", "take_treasure", "delve_rest",
    "fight_guardian", "slip_past", "attempt_trial", "face_shade", "take_remains",
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
        return lines

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

