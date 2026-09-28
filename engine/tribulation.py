"""A tribulation in the engine (phase 5f spec 5, 7): heaven's waves one at a time, and nothing else until they pass."""

import systems.tribulation_waves as TW
import systems.tribulations as TR
from engine.actions import Action, Choice
from engine.heart_page import demon_words
import systems.demons as D

WAVE_VERBS = frozenset({"wave", "heart_trial", "help", "journal", "unknown", "ambiguous"})
NTH = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth")


class TribulationMixin:
    def _gate(self, action):
        if TR.pending(self.world, self.player.id) is not None and action.verb not in WAVE_VERBS:
            return self._turn([("Heaven's tribulation is upon you. There is nothing else now.", "system")]
                              + self._wave_lines())
        return super()._gate(action)

    def _special_choices(self):
        now = TW.current(self.world, self.player.id)
        if now is None:
            return super()._special_choices()
        world, me, here = self.world, self.player.id, self.place.id
        kind, strength = now
        if kind == "demon":
            return [Choice("Face it", Action("wave", "face")), Choice("Bury it", Action("wave", "bury"))], []
        choices = [Choice("Endure it", Action("wave", "endure"))]
        choices += [Choice(f"Swallow {p.name} against it", Action("wave", ("spend", p.id)))
                    for p in TW.pills_for(world, me, strength)[:5]]
        if TW.shelter_of(world, me, here) is not None:
            choices.append(Choice("Shelter under the tribulation array", Action("wave", "shelter")))
        return choices, []

    def _wave_lines(self) -> list:
        """The wave to come, told."""
        t = TR.pending(self.world, self.player.id)
        now = TW.current(self.world, self.player.id)
        if now is None:
            return []
        kind, _ = now
        nth = NTH[t["wave"]] if t["wave"] < len(NTH) else "next"
        what = {"lightning": "heaven's lightning gathers", "fire": "heavenly fire pours down"}.get(kind)
        if kind == "demon":
            demon = D.heaviest(self.world, self.player.id)
            what = f"{demon_words(self.world, demon)} rises in the storm" if demon else "your heart is tried"
        return [(f"The {nth} wave of {len(t['waves'])}: {what}.", "system")]

    def _do_wave(self, target):
        world, me, here = self.world, self.player.id, self.place.id
        choice, item = target if isinstance(target, tuple) and len(target) == 2 else (target, None)
        if (why := TW.wave_block(world, me, here, choice, item)) is not None:
            return self._turn([(why, "system")] + self._wave_lines())
        return self._turn(self._commit(TW.wave_events(world, me, here, choice, item)) + self._wave_lines())

    def _do_heart_trial(self, choice):
        if TR.pending(self.world, self.player.id) is not None:  # a demon wave is faced as the heart's trial is
            return self._do_wave(choice)
        return super()._do_heart_trial(choice)

    def _after_commit(self, ids: list, events: list) -> list:
        lines = super()._after_commit(ids, events)
        if any(e.kind == "tribulation_gathers" for e in events):
            lines += self._wave_lines()
        return lines
