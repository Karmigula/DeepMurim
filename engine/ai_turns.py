"""A typed line's accepted changes made into a turn (phase 6 spec 14.5-14.6).

The model's proposals are checked by `ai/validate.py`; what stands comes here as ordinary events, and at most one
engine action (a choice of this turn, run as if chosen). The turn's lines are the engine's own short record of each
change (each event's outcome lines, never the grammar's), then the action's own lines.
"""

from engine.actions import Turn


class AiTurnsMixin:
    def apply_proposals(self, events: list, action=None) -> Turn:
        self.last_briefs, self._narrated = [], []
        lines = []
        if events:
            self._commit(events)
            lines = [(text, "dim") for brief in self.last_briefs for text in brief.outcome]
        briefs = list(self.last_briefs)
        if action is not None:
            turn = self.perform(action)
            turn.lines[:0] = lines
            turn.narrated = [i + len(lines) for i in turn.narrated]
            self.last_briefs = briefs + self.last_briefs
            return turn
        turn = self._after_turn(self._turn(lines))
        turn.narrated = []  # the model's paragraph is this turn's prose; nothing is narrated again
        return turn
