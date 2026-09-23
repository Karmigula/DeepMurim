"""The sect's seasons in the engine (phase 3c spec 6): catching up when you come home."""

import systems.founding as founding
import systems.sect_seasons as seasons
from world.events import Event


class SeasonsMixin:
    def _sect_catch_up(self) -> list:
        sect = founding.my_sect(self.world, self.player.id)
        if sect is None:
            return []
        lines = []
        for _ in range(seasons.MAX_SEASONS):
            events = seasons.season_events(self.world, self.player.id, sect)
            if not events:
                break
            lines += self._commit(events)
            if founding.my_sect(self.world, self.player.id) is None:
                break
        waiting = self.player.data.get("gate_challenger")
        if waiting and self.combat is None and self.encounter is None and self.challenger is None \
                and not self.world.entity(waiting).data.get("dead"):
            self.world.update_data(self.player.id, gate_challenger=None)
            lines += self._commit([Event("challenge_issued", (self.player.id, waiting), self.place.id, {"gate": True})])
            self.challenger = waiting
        return lines

    def _at_seat(self) -> bool:
        sect = founding.my_sect(self.world, self.player.id)
        return sect is not None and self.world.entity(sect).data["seat"] == self.place.id

    def _after_look(self) -> list:
        return super()._after_look() + (self._sect_catch_up() if self._at_seat() else [])

    def _after_arrival(self) -> list:
        return super()._after_arrival() + (self._sect_catch_up() if self._at_seat() else [])
