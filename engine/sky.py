"""The sky in the engine (phase 4d spec 7): the player's tribulation and the beast hunt.

Tasks 4 and 6 add the treasure race, the sky and rankings pages, and what arrival shows.
"""

import systems.events.beast_tide as beast_tide
import systems.events.tribulation as tribulation
import systems.races as races
from engine.actions import Action, Choice
from narrate.sky_text import race_line
from world.events import Event, commit


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
        if entry is None or len(entry.actors) < 2:
            return lines
        if data.get("result") != "won":
            race = (data.get("purpose") or {}).get("race")
            return lines + (self._race_fought(race, entry.actors[1], False) if race is not None else [])
        foe = self.world.entity(entry.actors[1])
        race = (data.get("purpose") or {}).get("race")
        if race is not None:
            return lines + self._race_fought(race, foe.id, True)
        if foe is not None and foe.data.get("beast"):
            events = beast_tide.hunt_events(self.world, self.player.id, self.place.id)
            lines += self._commit(events) if events else []
        return lines

    # --- treasure races and treasures (phase 4d spec 5) ---------------------------------------
    def _race_fought(self, race: int, champion: int, won: bool) -> list:
        me, town = self.player.id, self.place.id
        lines = self._commit([Event("race_fought", (me, champion), town, {"occurrence": race, "won": won})])
        if won and races.next_champion(self.world, race, me) is None:
            lines += self._commit(races.claim_events(self.world, race, me, town))
        return lines

    def _do_seek(self, _target):
        world, me, town = self.world, self.player.id, self.place.id
        race = races.race_here(world, town)
        if race is None:
            near = races.races_near(world, town)
            if not near:
                return self._turn([("No treasure light stands anywhere you can see.", "system")])
            return self._turn([(race_line(world, occurrence, distance), "dim") for occurrence, distance in near])
        if me in world.entity(race).data["data"]["out"]:
            return self._turn([("You have had your chance at this treasure.", "system")])
        foe = races.next_champion(world, race, me)
        if foe is None:
            return self._turn(self._commit(races.claim_events(world, race, me, town)))
        return self._turn([(f"{world.entity(foe).name} stands between you and the treasure.", "dim")]
                          + self._start_duel(foe, "duel", purpose={"race": race}))

    def _treasures(self) -> list:
        found = [self.world.entity(i) for i in self.world.targets(self.player.id, "owns")]
        return [t for t in found if t is not None and t.kind == "treasure"]

    def _general_extras(self) -> list:
        extras = super()._general_extras()
        if races.race_here(self.world, self.place.id) is not None:
            extras.append(Choice("Seek the treasure", Action("seek")))
        for item in self._treasures():
            if item.data["kind"] == "pill":
                extras.append(Choice(f"Swallow {item.name}", Action("swallow", item.id)))
            else:
                extras.append(Choice(f"Sell {item.name} ({item.data['value']} silver)", Action("sell_treasure", item.id)))
        return extras

    def _owned_treasure(self, item, kinds):
        found = [t for t in self._treasures() if t.data["kind"] in kinds and (item is None or t.id == item)]
        return found[0] if found else None

    def _do_swallow(self, item):
        pill = self._owned_treasure(item, ("pill",))
        if pill is None:
            return self._turn([("You have no pill to swallow.", "system")])
        return self._turn(self._commit(races.swallow_events(self.world, self.player.id, self.place.id, pill.id)))

    def _do_sell_treasure(self, item):
        found = self._owned_treasure(item, ("pill", "herb", "star_iron"))
        if found is None:
            return self._turn([("You have no treasure to sell.", "system")])
        return self._turn(self._commit(races.sell_events(self.world, self.player.id, self.place.id, found.id)))
