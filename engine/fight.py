"""Fights in the engine (phase 2 spec §9): starting, exchanging, verdicts, and what the screen shows."""

import systems.duel as duel
import systems.talk as talk
from engine.actions import Action, Choice
from systems.combat_core import INTENTS, QI_OUTPUTS, condition_of
from systems.realms import realm_title
from systems.techniques import martial_arts, usable
from world.gen.materialize import people_at

FIGHT_VERBS = frozenset({
    "intent", "use_menu", "use", "qi_output", "yield_duel", "flee", "verdict",
    "help", "journal", "unknown", "ambiguous", "back",
})
INTENT_LABELS = {"strike": "Strike", "feint": "Feint", "guard": "Guard", "probe": "Probe for an opening"}
NOT_FIGHTING = "You are not fighting anyone."
DECIDE = "Decide their fate first."


class FightMixin:
    # --- state and gating ----------------------------------------------------------
    def _restore(self) -> None:
        super()._restore()
        self.combat = duel.active_duel(self.world, self.player.id)

    def _gate(self, action):
        if self.combat is not None and action.verb not in FIGHT_VERBS:
            name = self.world.entity(self.combat.opponent).name
            return self._turn([(f"You are fighting {name}. Finish the fight first.", "system")])
        return super()._gate(action)

    # --- menus ----------------------------------------------------------------------------
    def _special_choices(self):
        if self.combat is None:
            return super()._special_choices()
        uses = self._use_choices()
        if self.combat.stage == "verdict":
            return self._verdict_choices(), []
        if self.submenu == "use_menu":
            return uses + [Choice("Back", Action("back"))], []
        return self._fight_choices(), uses

    def _fight_choices(self) -> list[Choice]:
        d = self.combat
        art = self.world.entity(d.technique).name if d.technique else "bare hands"
        return [Choice(INTENT_LABELS[i], Action("intent", i)) for i in INTENTS] + [
            Choice(f"Change technique (now: {art})...", Action("use_menu")),
            Choice(f"Qi output: {d.output} (change)", Action("qi_output")),
            Choice("Yield", Action("yield_duel")),
            Choice("Flee", Action("flee")),
        ]

    def _use_choices(self) -> list[Choice]:
        body = self.body()
        arts = [a for a in martial_arts(self.world, self.player.id) if usable(body, a.technique.data)]
        choices = [Choice(f"Fight with the {a.name}", Action("use", a.technique.id)) for a in arts]
        return choices[:7] + [Choice("Fight bare-handed", Action("use", "bare"))]

    def _verdict_choices(self) -> list[Choice]:
        opponent = self.world.entity(self.combat.opponent)
        if opponent.data.get("beast"):
            return [Choice(f"Let {opponent.name} limp away", Action("verdict", "spare"))]
        return [
            Choice(f"Spare {opponent.name}", Action("verdict", "spare")),
            Choice(f"Rob {opponent.name}", Action("verdict", "rob")),
            Choice(f"Cripple {opponent.name}", Action("verdict", "cripple")),
        ]

    def _conversation_extras(self, npc) -> list:
        extras = []
        if not npc.data.get("beast"):
            if len(talk.conversations_with(self.world, npc.id, self.player.id)) >= 2:
                extras.append(Choice("Offer to spar", Action("spar", npc.id)))
            extras.append(Choice("Challenge them to a duel", Action("challenge", npc.id)))
        return extras + super()._conversation_extras(npc)

    # --- starting ---------------------------------------------------------------------------
    def _start_duel(self, opponent: int, mode: str, purpose: dict | None = None, opening: str | None = None) -> list:
        events = duel.start_events(self.world, self.player.id, opponent, self.place.id, mode, purpose, opening)
        lines = self._commit(events)
        self.combat = duel.Duel.from_event(self._last_ids[0], events[0])
        self.focus, self.submenu = None, None
        return lines

    def _offer_fight(self, npc_id, mode: str):
        npc_id = npc_id if npc_id is not None else self.focus
        present = {p.id for p in people_at(self.world, self.place.id, exclude=self.player.id)}
        if npc_id not in present:
            return self._turn([("There is no one like that here.", "system")])
        if not duel.accepts(self.world, npc_id, self.player.id, mode):
            return self._turn(self._commit(duel.refusal_events(self.player.id, npc_id, self.place.id, mode)))
        return self._turn(self._start_duel(npc_id, mode))

    def _do_spar(self, npc_id):
        return self._offer_fight(npc_id, "spar")

    def _do_challenge(self, npc_id):
        return self._offer_fight(npc_id, "duel")

    # --- fighting -----------------------------------------------------------------------------
    def _exchange(self, intent: str):
        events = duel.exchange_events(self.world, self.combat, intent)
        lines = self._commit(events)
        duel.apply_record(self.combat, events[0].data)
        if len(events) > 1:
            lines += self._finish_duel(events[-1].data)
        return self._turn(lines)

    def _do_intent(self, intent):
        if self.combat is None:
            return self._turn([(NOT_FIGHTING, "system")])
        if self.combat.stage == "verdict":
            return self._turn([(DECIDE, "system")])
        if intent not in INTENTS:
            return self._turn([("Strike, feint, guard or probe?", "system")])
        return self._exchange(intent)

    def _do_flee(self, _target):
        if self.combat is None:
            return self._turn([(NOT_FIGHTING, "system")])
        if self.combat.stage == "verdict":
            return self._turn([(DECIDE, "system")])
        return self._exchange("flee")

    def _do_yield_duel(self, _target):
        if self.combat is None:
            return self._turn([(NOT_FIGHTING, "system")])
        if self.combat.stage == "verdict":
            return self._turn([("You have already won. " + DECIDE, "system")])
        events = duel.yield_events(self.world, self.combat)
        lines = self._commit(events)
        return self._turn(lines + self._finish_duel(events[-1].data))

    def _do_verdict(self, choice):
        if self.combat is None or self.combat.stage != "verdict":
            return self._turn([("There is no one at your mercy.", "system")])
        events = duel.verdict_events(self.world, self.combat, choice)
        if not events:
            return self._turn([("Spare, rob or cripple?", "system")])
        lines = self._commit(events)
        return self._turn(lines + self._finish_duel(events[-1].data))

    def _do_use_menu(self, _target):
        if self.combat is None:
            return self._turn([(NOT_FIGHTING, "system")])
        self.submenu = "use_menu"
        return self._turn([("Which art will you fight with?", "system")])

    def _do_use(self, technique):
        if self.combat is None:
            return self._turn([(NOT_FIGHTING, "system")])
        valid = {c.action.target for c in self._use_choices()}
        if technique not in valid:
            return self._turn([("You can't fight with that now.", "system")])
        self.combat.technique = None if technique == "bare" else technique
        name = "bare hands" if technique == "bare" else f"the {self.world.entity(technique).name}"
        self.submenu = None
        return self._turn([(f"You will fight with {name}.", "system")])

    def _do_qi_output(self, _target):
        if self.combat is None:
            return self._turn([(NOT_FIGHTING, "system")])
        d = self.combat
        d.output = QI_OUTPUTS[(QI_OUTPUTS.index(d.output) + 1) % len(QI_OUTPUTS)]
        return self._turn([(f"You will put {d.output} qi behind your moves.", "system")])

    def _finish_duel(self, data: dict) -> list:
        self.combat, self.submenu = None, None
        return self._after_duel(data)

    # --- screen ---------------------------------------------------------------------------------
    def _special_art(self):
        if self.combat is None:
            return super()._special_art()
        opponent = self.world.entity(self.combat.opponent)
        harm = self.combat.harm["opponent"]
        return {"type": "duel", "parts": opponent.data.get("portrait"), "beast": bool(opponent.data.get("beast")),
                "harm": harm, "condition": condition_of(harm)}

    def _special_status(self):
        if self.combat is None:
            return super()._special_status()
        d, body = self.combat, self.body()
        opponent = self.world.entity(d.opponent).name
        art = self.world.entity(d.technique).name if d.technique else "bare hands"
        return (f"{self.player.name} | {realm_title(body)} | vs {opponent}: you {condition_of(d.harm['player'])}, "
                f"qi {body.qi:.0f} | them {condition_of(d.harm['opponent'])} | {art}, {d.output} qi")
