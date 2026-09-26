"""The player's investigation (phase 4h spec 3-7, 11): examine the body, ask, search, accuse, the founder's hall,
the will, and the framed heir's return."""

import systems.encounters as encounters
import systems.frames as R
import systems.legitimacy as L
import systems.lives as lives
import systems.murder as M
import systems.plots as P
import systems.puppets as U
import systems.scheming as S
import systems.succession_crisis as SC
from systems.founding import followers
from engine.actions import Action, Choice
from world.events import commit

ASKS = {"night": "Ask about the night the master died", "silver": "Ask about the gift they took",
        "envoy": "Ask where they have come from", "scribe": "Ask about the will they wrote",
        "false_witness": "Ask about the crime they swore to", "seen": "Ask what they saw outside the walls"}


class IntrigueMixin:
    def _crises_here(self) -> list:
        """Live crises whose seat is this town (anyone at the seat may look into them)."""
        out = []
        for faction in self.world.entities_after("faction", "crisis", 0):
            occurrence = SC.live(self.world, faction.id)
            if occurrence is not None and occurrence.data["place"] == self.place.id:
                out.append(occurrence)
        return out

    def _seated_here(self) -> list[int]:
        return [f for f in self.world.entity(self.place.id).data.get("seats", [])
                if not self.world.entity(f).data.get("dissolved")]

    def _general_extras(self) -> list:
        extras = super()._general_extras()
        world, me = self.world, self.player.id
        for occurrence in self._crises_here():
            if M.examine_block(world, occurrence, me) is None:
                extras.append(Choice("Examine the late master's body", Action("examine_body", occurrence.id)))
            if L.test_block(world, occurrence, me) is None:
                extras.append(Choice("Enter the founder's hall and face the test", Action("founder_test", occurrence.id)))
            if R.examine_will_block(world, occurrence, me) is None:
                extras.append(Choice("Examine the will that was read", Action("examine_will", occurrence.id)))
        for suspect in sorted(P.suspicions(world, me)):
            if P.search_block(world, me, suspect) is None:
                extras.append(Choice(f"Search {world.entity(suspect).name}'s quarters", Action("search_quarters", suspect)))
            for faction in self._seated_here():
                if P.accuse_block(world, me, suspect, faction) is None:
                    extras.append(Choice(f"Accuse {world.entity(suspect).name} before the elders",
                                         Action("accuse", (suspect, faction))))
        for occurrence in self._crises_here():  # the schemes (spec 8)
            crisis = SC.crisis_of(occurrence)
            if S.forge_block(world, me, occurrence) is None:
                for c in SC.standing_claimants(world, crisis):
                    who = "yourself" if c["person"] == me else world.entity(c["person"]).name
                    extras.append(Choice(f"Have a will forged naming {who} ({S.FORGE_PRICE} silver)",
                                         Action("forge_will", (occurrence.id, c["person"]))))
            for c in SC.standing_claimants(world, crisis):
                if S.frame_block(world, me, occurrence, c["person"]) is None:
                    extras.append(Choice(f"Plant false evidence against {world.entity(c['person']).name} "
                                         f"({S.FRAME_PRICE} silver)", Action("frame_rival", (occurrence.id, c["person"]))))
                if S.fund_block(world, me, occurrence, c["person"]) is None:
                    extras.append(Choice(f"Put silver behind {world.entity(c['person']).name}'s claim "
                                         f"({S.fund_price(world, crisis['faction'])} silver)",
                                         Action("fund_claim", (occurrence.id, c["person"]))))
        for faction in self._seated_here():
            for follower in followers(world, me):
                if S.spy_block(world, me, follower, faction) is None:
                    extras.append(Choice(f"Send {world.entity(follower).name} to join the "
                                         f"{world.entity(faction).name} in secret ({S.SPY_PRICE} silver)",
                                         Action("plant_spy", (follower, faction))))
        framed = self.player.data.get("framed") or {}
        if framed and P.search_block(world, me, me) is None:
            extras.append(Choice("Search your old quarters", Action("search_quarters", me)))
        for faction in self._seated_here():  # an exile's quarters, for one who has found a thread of the frame
            for plot in P.plots_of(world, faction, ("frame",)):
                exile = plot.data["target"]
                if exile != me and P.found_by(world, plot, me) and P.search_block(world, me, exile) is None                         and exile not in P.suspicions(world, me):
                    extras.append(Choice(f"Search the quarters {world.entity(exile).name} left behind",
                                         Action("search_quarters", exile)))
        if framed and R.player_return_block(world, me, self.place.id) is None:
            extras.append(Choice(f"Demand the seat of the {world.entity(framed['faction']).name} you were cast out of",
                                 Action("return_seat", framed["faction"])))
        return extras

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        world, me = self.world, self.player.id
        if M.witness_plot(world, me, npc.id) is not None:
            extras.append(Choice(ASKS["night"], Action("ask_clue", (npc.id, "witness"))))
        if U.gift_plot(world, me, npc.id) is not None:
            extras.append(Choice(ASKS["silver"], Action("ask_clue", (npc.id, "silver"))))
        if U.envoy_plot(world, me, npc.id) is not None:
            extras.append(Choice(ASKS["envoy"], Action("ask_clue", (npc.id, "envoy"))))
        if S.buy_poison_block(world, me, npc.id) is None:
            extras.append(Choice(f"Buy a poison ({S.POISON_PRICE} silver)", Action("buy_poison", npc.id)))
        if S.poison_block(world, me, npc.id) is None:
            extras.append(Choice("Slip poison into their tea", Action("slip_poison", npc.id)))
        for kind, label in (("scribe", ASKS["scribe"]), ("false_witness", ASKS["false_witness"]), ("night", ASKS["seen"])):
            plot = R.ask_plot(world, me, npc.id, kind)
            if plot is not None and SC.live(world, plot.data["faction"]) is not None:  # people talk in a crisis
                extras.append(Choice(label, Action("ask_clue", (npc.id, kind))))
        return extras

    def _occurrence_here(self, occurrence_id):
        found = [o for o in self._crises_here() if o.id == occurrence_id]
        return found[0] if found else None

    def _do_examine_body(self, occurrence_id):
        if occurrence_id is None:  # typed: the crisis here, if one
            occurrence_id = next((o.id for o in self._crises_here()), None)
        occurrence = self._occurrence_here(occurrence_id)
        if occurrence is None or (why := M.examine_block(self.world, occurrence, self.player.id)) is not None:
            return self._turn([(why if occurrence else "There is no one lying in state here.", "system")])
        return self._turn(self._commit(M.examine_events(self.world, occurrence, self.player.id)))

    def _do_examine_will(self, occurrence_id):
        occurrence = self._occurrence_here(occurrence_id)
        if occurrence is None or (why := R.examine_will_block(self.world, occurrence, self.player.id)) is not None:
            return self._turn([(why if occurrence else "No will has been read here.", "system")])
        return self._turn(self._commit(R.examine_will_events(self.world, occurrence, self.player.id)))

    def _do_founder_test(self, occurrence_id):
        occurrence = self._occurrence_here(occurrence_id)
        if occurrence is None or (why := L.test_block(self.world, occurrence, self.player.id)) is not None:
            return self._turn([(why if occurrence else "There is no founder's hall open to you here.", "system")])
        return self._turn(self._commit(L.test_events(self.world, occurrence, self.player.id)))

    def _do_search_quarters(self, suspect):
        if not isinstance(suspect, int) or (why := P.search_block(self.world, self.player.id, suspect)) is not None:
            return self._turn([(why if isinstance(suspect, int) else "Whose quarters?", "system")])
        return self._turn(self._commit(P.search_events(self.world, self.player.id, suspect, self.place.id)))

    def _do_accuse(self, target):
        suspect, faction = target if isinstance(target, tuple) else (target, None)
        if faction is None:
            faction = next((f for f in self._seated_here() if P.accuse_block(self.world, self.player.id, suspect, f)
                            is None), None)
        if faction is None or (why := P.accuse_block(self.world, self.player.id, suspect, faction)) is not None:
            return self._turn([(why if faction is not None else "There are no elders here to hear you.", "system")])
        events = P.accuse_events(self.world, self.player.id, suspect, faction, self.place.id)
        lines = self._commit_quiet(events)
        if events[0].kind == "false_accusation" and SC.PROUD & set(self.world.entity(suspect).data.get("traits", ())) \
                and self.place.id in self.world.targets(suspect, "located_in"):
            lines += self._commit(encounters.challenge_events(self.player.id, suspect, self.place.id))
            self.challenger = suspect  # a proud man falsely accused calls you out
        return self._turn(lines)

    def _commit_quiet(self, events: list) -> list:
        """The player's deeds narrated; the world's events (no actors) committed without a line."""
        lines = []
        for event in events:
            if event.actors:
                lines += self._commit([event])
            else:
                commit(self.world, [event])
        return lines

    def _do_ask_clue(self, target):
        npc, kind = target if isinstance(target, tuple) else (None, None)
        if npc is None or self.focus != npc:
            return self._turn([("Speak with them first.", "system")])
        world, me, here = self.world, self.player.id, self.place.id
        if kind == "witness":
            events = M.night_events(world, me, npc, here)
        elif kind in ("silver", "envoy"):
            events = U.asked_events(world, me, npc, here, kind)
        else:
            events = R.asked_events(world, me, npc, here, kind)
        return self._turn(self._commit(events))

    def _do_return_seat(self, faction):
        if (why := R.player_return_block(self.world, self.player.id, self.place.id)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit_quiet(R.return_events(self.world, self.player.id,
                                                             lives.current_season(self.world))))

    # --- the schemes (spec 8) ------------------------------------------------------------------------------

    def _scheme_target(self, target):
        occurrence_id, person = target if isinstance(target, tuple) else (None, None)
        return self._occurrence_here(occurrence_id), person

    def _do_forge_will(self, target):
        occurrence, names = self._scheme_target(target)
        if occurrence is None or (why := S.forge_block(self.world, self.player.id, occurrence)) is not None:
            return self._turn([(why if occurrence else "There is no crisis here.", "system")])
        return self._turn(self._commit_quiet(S.forge_events(self.world, self.player.id, occurrence, names)))

    def _do_frame_rival(self, target):
        occurrence, rival = self._scheme_target(target)
        if occurrence is None or (why := S.frame_block(self.world, self.player.id, occurrence, rival)) is not None:
            return self._turn([(why if occurrence else "There is no crisis here.", "system")])
        return self._turn(self._commit_quiet(S.frame_events(self.world, self.player.id, occurrence, rival)))

    def _do_fund_claim(self, target):
        occurrence, claimant = self._scheme_target(target)
        if occurrence is None or (why := S.fund_block(self.world, self.player.id, occurrence, claimant)) is not None:
            return self._turn([(why if occurrence else "There is no crisis here.", "system")])
        return self._turn(self._commit_quiet(S.fund_events(self.world, self.player.id, occurrence, claimant)))

    def _do_plant_spy(self, target):
        follower, faction = target if isinstance(target, tuple) else (None, None)
        if follower is None or (why := S.spy_block(self.world, self.player.id, follower, faction)) is not None:
            return self._turn([(why if follower is not None else "Send whom?", "system")])
        return self._turn(self._commit_quiet(S.spy_events(self.world, self.player.id, follower, faction, self.place.id)))

    def _do_buy_poison(self, npc):
        if self.focus != npc or (why := S.buy_poison_block(self.world, self.player.id, npc)) is not None:
            return self._turn([(why if self.focus == npc else "Speak with them first.", "system")])
        return self._turn(self._commit(S.buy_poison_events(self.world, self.player.id, npc, self.place.id)))

    def _do_slip_poison(self, npc):
        if self.focus != npc or (why := S.poison_block(self.world, self.player.id, npc)) is not None:
            return self._turn([(why if self.focus == npc else "Speak with them first.", "system")])
        lines = self._commit_quiet(S.poison_events(self.world, self.player.id, npc, self.place.id))
        self.focus = None  # they will not finish the conversation
        return self._turn(lines)
