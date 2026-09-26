"""Succession crises in the engine (phase 4g spec 6, 7): claim, declare, sway, champion, search, trade the token."""

import systems.crisis_play as P
import systems.regency as R
import systems.claimants as C
import systems.succession_crisis as SC
import systems.testament as T
from systems.beliefs import known_people
from world.gen.materialize import people_at
from engine.actions import Action, Choice
from systems import factions as F
from world.events import Event, commit

SWAY_LABELS = {"speak": "Speak to them for {name}", "gift": "Offer them a gift for {name} ({silver} silver)",
               "threat": "Lean on them for {name}", "favour": "Ask what favour would win them for {name}"}


class CrisisMixin:
    def _nameable_claimants(self, crisis: dict) -> list[dict]:
        """The standing claimants a choice may name: those heard of or met, those here, and yourself (5a review)."""
        world, me = self.world, self.player.id
        known = set(known_people(world, me)) | {p.id for p in people_at(world, self.place.id)} | {me}
        return [c for c in SC.standing_claimants(world, crisis) if c["person"] in known]

    def _crisis_here(self):
        return P.mine_here(self.world, self.player.id, self.place.id)

    def _general_extras(self) -> list:
        extras = super()._general_extras()
        world, me = self.world, self.player.id
        occurrence = self._crisis_here()
        if occurrence is not None:
            crisis = SC.crisis_of(occurrence)
            faction = world.entity(crisis["faction"]).name
            if P.claim_block(world, occurrence, me) is None:
                extras.append(Choice(f"Claim the seat of the {faction}", Action("claim_seat", occurrence.id)))
            for c in self._nameable_claimants(crisis):
                person = c["person"]
                if P.declare_block(world, occurrence, me, person) is None:
                    extras.append(Choice(f"Declare for {world.entity(person).name}", Action("declare_for", person)))
                if P.champion_block(world, occurrence, me, person) is None:
                    extras.append(Choice(f"Offer to fight as {world.entity(person).name}'s champion",
                                         Action("champion_for", person)))
            if P.search_block(world, occurrence, me) is None:
                extras.append(Choice("Search the late master's chambers", Action("search_chambers", occurrence.id)))
            will = crisis.get("will") or {}
            if will.get("holder") == me and will.get("state") == "held":
                extras.append(Choice("Read out the late master's will", Action("reveal_will", occurrence.id)))
                extras.append(Choice("Burn the late master's will", Action("burn_will", occurrence.id)))
            trial = P.my_trial(world, occurrence, me)
            if trial is not None:
                extras.append(Choice(f"Fight the trial against {world.entity(trial[1]).name}",
                                     Action("fight_trial", occurrence.id)))
            for token in P.tokens_held_by(world, me):
                if world.entity(token).data["faction"] == crisis["faction"]:
                    for c in self._nameable_claimants(crisis):
                        if c["person"] != me:
                            extras.append(Choice(f"Hand the leader's token to {world.entity(c['person']).name}",
                                                 Action("hand_token", (token, c["person"]))))
        for token in P.tokens_lying_at(world, self.place.id):
            extras.append(Choice(f"Pick up {world.entity(token).name}", Action("take_token", token)))
        for fid in R.led_by(world, me):
            if world.entity(fid).data["seat"] == self.place.id and SC.live(world, fid) is None:
                for successor in R.successors(world, me, fid):
                    extras.append(Choice(f"Step down in favour of {world.entity(successor).name}",
                                         Action("step_down", (fid, successor))))
        for fid, _, data in F.memberships(world, me):
            if world.entity(fid).data.get("seat") == self.place.id and R.reclaim_block(world, me, fid) is None:
                extras.append(Choice(f"Reclaim the seat of the {world.entity(fid).name}", Action("reclaim_seat", fid)))
        return extras

    def _before_scene(self) -> None:
        super()._before_scene()
        for fid in R.visit(self.world, self.player.id, self.place.id):
            events = R.return_events(self.world, self.player.id, fid)
            if events:
                self._pending += self._commit_all(events)

    def _do_step_down(self, target):
        if target is None:  # typed: say who may take the seat
            options = [c.label for c in self._general_extras() if c.action.verb == "step_down"]
            return self._turn([("Step down in favour of whom?" if options else "You lead no sect here.", "system")])
        fid, successor = target if isinstance(target, tuple) else (None, None)
        if fid not in R.led_by(self.world, self.player.id) or successor not in R.successors(self.world, self.player.id, fid):
            return self._turn([("You cannot hand the seat to them.", "system")])
        return self._turn(self._commit_all(R.step_down_events(self.world, self.player.id, fid, successor)))

    def _do_reclaim_seat(self, fid):
        if (why := R.reclaim_block(self.world, self.player.id, fid)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit_all(R.reclaim_events(self.world, self.player.id, fid)))

    def _do_name_chief(self, npc):
        fid = next((f for f in R.led_by(self.world, self.player.id)
                    if C.role_in(self.world, npc, f) in ("keeper", "disciple")), None)
        if fid is None or self.focus != npc:
            return self._turn([("You cannot name them.", "system")])
        seat = self.world.entity(fid).data["seat"]
        return self._turn(self._commit([Event("named_chief", (npc,), seat, {"faction": fid, "season": 0})]))

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        world, me = self.world, self.player.id
        occurrence = self._crisis_here()
        if occurrence is not None:
            crisis = SC.crisis_of(occurrence)
            toward = P.sway_for(world, occurrence, me)
            for way, label in SWAY_LABELS.items():
                if toward is not None and P.sway_block(world, occurrence, me, npc.id, way) is None:
                    name = "yourself" if toward == me else world.entity(toward).name
                    silver = P.gift_price(world, crisis, npc.id) if way == "gift" else 0
                    extras.append(Choice(label.format(name=name, silver=silver), Action("sway", (npc.id, way))))
            will = crisis.get("will") or {}
            if will.get("holder") == npc.id and will.get("state") == "held":
                extras.append(Choice("Challenge them for the late master's will", Action("duel_for_will", npc.id)))
        for fid in R.led_by(world, me):
            if C.role_in(world, npc.id, fid) in ("keeper", "disciple") and world.entity(fid).data.get("heir") != npc.id:
                extras.append(Choice(f"Name them chief disciple of the {world.entity(fid).name}",
                                     Action("name_chief", npc.id)))
        for token in P.tokens_held_by(world, npc.id):
            if P.buy_block(world, token, me, npc.id) is None:
                extras.append(Choice(f"Buy {world.entity(token).name} ({P.token_price(world, token)} silver)",
                                     Action("buy_sect_token", (npc.id, token))))
            faction = world.entity(token).data["faction"]
            if C.role_in(world, npc.id, faction) != "leader" or SC.live(world, faction) is not None:  # not a master's own
                extras.append(Choice(f"Challenge them for {world.entity(token).name}", Action("duel_for_token", (npc.id, token))))
        return extras

    def _commit_all(self, events: list) -> list:
        """The player's deeds narrated; a crisis the world starts (no actors) committed quietly (4f's rule)."""
        lines = []
        for event in events:
            if event.actors:
                lines += self._commit([event])
            else:
                commit(self.world, [event])
        return lines

    def _crisis_or_say(self):
        occurrence = self._crisis_here()
        return occurrence, (None if occurrence is not None else self._turn([("There is no crisis here.", "system")]))

    def _do_claim_seat(self, _target):
        occurrence, no = self._crisis_or_say()
        if no:
            return no
        if (why := P.claim_block(self.world, occurrence, self.player.id)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(P.claim_events(self.world, occurrence, self.player.id)))

    def _do_declare_for(self, claimant):
        occurrence, no = self._crisis_or_say()
        if no:
            return no
        if (why := P.declare_block(self.world, occurrence, self.player.id, claimant)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(P.declare_events(self.world, occurrence, self.player.id, claimant)))

    def _do_champion_for(self, claimant):
        occurrence, no = self._crisis_or_say()
        if no:
            return no
        if (why := P.champion_block(self.world, occurrence, self.player.id, claimant)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(P.champion_events(self.world, occurrence, self.player.id, claimant)))

    def _do_sway(self, target):
        occurrence, no = self._crisis_or_say()
        if no:
            return no
        voter, way = target if isinstance(target, tuple) else (self.focus, "speak")
        if self.focus != voter:
            return self._turn([("Speak with them first.", "system")])
        if (why := P.sway_block(self.world, occurrence, self.player.id, voter, way)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(P.sway_events(self.world, occurrence, self.player.id, voter, way)))

    def _do_search_chambers(self, _target):
        occurrence, no = self._crisis_or_say()
        if no:
            return no
        if (why := P.search_block(self.world, occurrence, self.player.id)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(P.search_events(self.world, occurrence, self.player.id)))

    def _do_reveal_will(self, _target):
        return self._will(False)

    def _do_burn_will(self, _target):
        return self._will(True)

    def _will(self, burn: bool):
        occurrence, no = self._crisis_or_say()
        if no:
            return no
        events = P.will_events(self.world, occurrence, self.player.id, burn)
        return self._turn(self._commit(events) if events else [("You hold no will.", "system")])

    def _do_fight_trial(self, _target):
        occurrence, no = self._crisis_or_say()
        if no:
            return no
        trial = P.my_trial(self.world, occurrence, self.player.id)
        if trial is None:
            return self._turn([("No trial waits for you.", "system")])
        return self._turn(self._start_duel(trial[1], "duel", purpose={"crisis_trial": occurrence.id}))

    def _do_duel_for_will(self, holder):
        occurrence, no = self._crisis_or_say()
        if no:
            return no
        will = SC.crisis_of(occurrence).get("will") or {}
        if will.get("holder") != holder or holder is None:
            return self._turn([("They do not hold it.", "system")])
        return self._turn(self._start_duel(holder, "duel", purpose={"crisis_will": occurrence.id}))

    def _do_buy_sect_token(self, target):
        holder, token = target if isinstance(target, tuple) else (None, None)
        if token is None or (why := P.buy_block(self.world, token, self.player.id, holder)) is not None:
            return self._turn([(why if token is not None else "Buy what?", "system")])
        return self._turn(self._commit(P.token_events(self.world, token, self.player.id, self.place.id, "bought", holder)))

    def _do_duel_for_token(self, target):
        holder, token = target if isinstance(target, tuple) else (None, None)
        if token is None or T.holder(self.world, token) != holder:
            return self._turn([("They do not hold it.", "system")])
        return self._turn(self._start_duel(holder, "duel", purpose={"sect_token": token}))

    def _do_take_token(self, token):
        if token not in P.tokens_lying_at(self.world, self.place.id):
            return self._turn([("It is not here.", "system")])
        return self._turn(self._commit(P.token_events(self.world, token, self.player.id, self.place.id, "taken")))

    def _do_hand_token(self, target):
        token, claimant = target if isinstance(target, tuple) else (None, None)
        occurrence = self._crisis_here()
        if token not in P.tokens_held_by(self.world, self.player.id) or occurrence is None \
                or SC.claimant(SC.crisis_of(occurrence), claimant) is None:
            return self._turn([("You cannot hand that over here.", "system")])
        return self._turn(self._commit(P.token_events(self.world, token, self.player.id, self.place.id, "handed",
                                                      claimant)))

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        purpose = data.get("purpose") or {}
        entry = self.world.chronicle_entry(data["duel"]) if data.get("duel") else None
        if entry is None or len(entry.actors) < 2:
            return lines
        me, opponent = entry.actors[0], entry.actors[1]
        won = data.get("result") == "won"
        if "crisis_trial" in purpose:
            occurrence = self.world.entity(purpose["crisis_trial"])
            if P.my_trial(self.world, occurrence, me) is not None:
                lines += self._commit(P.trial_result_events(self.world, occurrence, me, won))
        elif "crisis_will" in purpose:
            events = P.will_duel_result_events(self.world, self.world.entity(purpose["crisis_will"]), me, won)
            lines += self._commit(events) if events else []
        elif "sect_token" in purpose and won and T.holder(self.world, purpose["sect_token"]) == opponent:
            lines += self._commit(P.token_events(self.world, purpose["sect_token"], me, self.place.id, "won", opponent))
        return lines
