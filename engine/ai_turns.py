"""A typed line's accepted changes made into a turn (phase 6 spec 14.5-14.6).

The model's proposals are checked by `ai/validate.py`; what stands comes here as ordinary events, and at most one
engine action (a choice of this turn, run as if chosen). The turn's lines are the engine's own short record of each
change (each event's outcome lines, never the grammar's), then the action's own lines. The whole turn is one
transaction: if the action fails, the changes are taken back with it (6c review).
"""

from ai.deeds import TALK_PER_PATIENCE
from engine.actions import Turn
from systems import talk


class AiTurnsMixin:
    ai_lines = 0  # how many of the last typed turn's first lines are the changes' own (AI only hides just those)

    def held(self) -> bool:
        """Held by a fight, a road's encounter, a challenge, heaven's waves or a heart trial: a typed line may only
        choose or feel then (6c minors)."""
        return (self.combat is not None or self.encounter is not None or self.challenger is not None
                or self._holding() or self.submenu == "heart_trial")

    def talk_wearies(self) -> Turn | None:
        """Spoken to past their patience in one conversation, they end it, as asking too much does (6c minors)."""
        npc, me = self.world.entity(self.focus), self.player.id
        said = 0
        for entry in self.world.chronicle_about(npc.id, limit=200):  # newest first, back to this greeting
            if entry.kind in ("met", "conversed") and me in entry.actors:
                break
            said += entry.kind == "talked" and entry.actors[0] == me
        if said < TALK_PER_PATIENCE * self._patience(npc):
            return None
        lines = self._commit(talk.lost_patience_events(me, npc.id, self.place.id, "talk"))
        self.focus = None
        return self._turn(lines)

    def _offered(self) -> set:
        return {choice.action for choice in sum(self._choices(), [])}

    def apply_proposals(self, events: list, action=None) -> Turn:
        with self.world.transaction():
            return self._apply_proposals(events, action)

    def _apply_proposals(self, events: list, action) -> Turn:
        self.last_briefs, self._narrated = [], []
        lines = []
        offered = self._offered() if action is not None and events else set()
        if events:
            self._commit(events)
            lines = [(text, "dim") for brief in self.last_briefs for text in brief.outcome]
        self.ai_lines = len(lines)
        briefs = list(self.last_briefs)
        if action in offered and action not in self._offered():
            lines.append(("That can no longer be done.", "dim"))  # the changes made it so (6c minors)
            action = None
        if action is not None:
            turn = self.perform(action)
            turn.lines[:0] = lines
            turn.narrated = [i + len(lines) for i in turn.narrated]
            self.last_briefs = briefs + self.last_briefs
            return turn
        turn = self._after_turn(self._turn(lines))
        turn.narrated = []  # the model's paragraph is this turn's prose; nothing is narrated again
        return turn
