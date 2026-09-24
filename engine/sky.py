"""The sky in the engine (phase 4d spec 7): the player's tribulation and the beast hunt.

Tasks 4 and 6 add the treasure race, the sky and rankings pages, and what arrival shows.
"""

import systems.events.beast_tide as beast_tide
import systems.events.tribulation as tribulation
from world.events import commit


class SkyMixin:
    def _commit_sky(self, events: list) -> list:
        """Occurrences start quietly (the scene shows the sky); the rest is narrated."""
        quiet = [e for e in events if e.kind == "sky_started"]
        if quiet:
            commit(self.world, quiet)
        loud = [e for e in events if e.kind != "sky_started"]
        return self._commit(loud) if loud else []

    def _after_commit(self, ids: list, events: list) -> list:
        lines = super()._after_commit(ids, events)
        for event in events:
            if event.kind == "breakthrough" and event.actors[0] == self.player.id and event.data.get("success") \
                    and event.data["realm_after"] >= tribulation.TRIBULATION_REALM:
                outcome = tribulation.player_roll(self.world, self.player.id)
                lines += self._commit_sky(tribulation.trigger_events(
                    self.world, self.player.id, self.place.id, event.data["realm_after"], outcome=outcome))
        return lines

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        entry = self.world.chronicle_entry(data["duel"]) if data.get("duel") else None
        if entry is None or data.get("result") != "won" or len(entry.actors) < 2:
            return lines
        foe = self.world.entity(entry.actors[1])
        if foe is not None and foe.data.get("beast"):
            events = beast_tide.hunt_events(self.world, self.player.id, self.place.id)
            lines += self._commit(events) if events else []
        return lines
