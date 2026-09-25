"""Tournaments in the engine (phase 4e spec 6): register, answer the herald, fight your bouts, hold the lei tai."""

import systems.tournaments as T
from engine.actions import Action, Choice
from narrate.tournament_text import KIND_NAMES


class TournamentMixin:
    def _general_extras(self) -> list:
        extras = super()._general_extras()
        world, me, town = self.world, self.player.id, self.place.id
        open_ = T.here(world, town, T.KINDS, ("announced",))
        if open_ is not None and T.register_block(world, open_, me) is None:
            kind = world.entity(open_).data["type"]
            extras.append(Choice(f"Enter {KIND_NAMES[kind]}", Action("register", open_)))
            if T.can_preside(world, open_, me):
                extras.append(Choice("Preside over the contest", Action("preside", open_)))
        call = T.player_call(world, me, town)
        if call is not None:
            name = world.entity(call[3]).name
            extras.append(Choice(f"Answer the herald: fight {name}", Action("bout", call[0])))
            extras.append(Choice("Forfeit your bout", Action("forfeit_bout", call[0])))
        platform = T.here(world, town, ("lei_tai",), ("active",))
        if platform is not None and T.lei_tai_open(world, platform, me):
            holder = world.entity(platform).data["data"]["holder"]
            extras.append(Choice(f"Challenge the platform holder, {world.entity(holder).name}",
                                 Action("challenge_lei_tai", platform)))
        return extras

    def _herald(self) -> list:
        call = T.player_call(self.world, self.player.id, self.place.id)
        if call is None:
            return []
        kind = self.world.entity(call[0]).data["type"]
        return [(f"The herald calls your name: today you fight {self.world.entity(call[3]).name} "
                 f"at {KIND_NAMES[kind]}.", "dim")]

    def _after_look(self) -> list:
        return super()._after_look() + self._herald()

    def _after_arrival(self) -> list:
        return super()._after_arrival() + self._herald()

    def _do_register(self, occurrence):
        why = T.register_block(self.world, occurrence, self.player.id) if isinstance(occurrence, int) else "There is nothing to enter here."
        if why:
            return self._turn([(why, "system")])
        return self._turn(self._commit(T.register_events(self.world, occurrence, self.player.id)))

    def _do_preside(self, occurrence):
        if not isinstance(occurrence, int) or not T.can_preside(self.world, occurrence, self.player.id) \
                or T.stage(self.world, occurrence) != "announced":
            return self._turn([("There is no contest of yours to preside over.", "system")])
        return self._turn(self._commit(T.register_events(self.world, occurrence, self.player.id, preside=True)))

    def _do_bout(self, occurrence):
        call = T.player_call(self.world, self.player.id, self.place.id)
        if call is None or call[0] != occurrence:
            return self._turn([("No herald has called your name.", "system")])
        occurrence, r, i, opponent = call
        purpose = {"tournament": occurrence, "round": r, "match": i}
        return self._turn(self._start_duel(opponent, "bout", purpose=purpose))

    def _do_forfeit_bout(self, occurrence):
        events = T.forfeit_events(self.world, occurrence, self.player.id) if isinstance(occurrence, int) else []
        if not events:
            return self._turn([("You have no bout to forfeit.", "system")])
        return self._turn(self._commit(events))

    def _do_challenge_lei_tai(self, occurrence):
        if not isinstance(occurrence, int) or not T.lei_tai_open(self.world, occurrence, self.player.id):
            return self._turn([("There is no platform you may challenge.", "system")])
        holder = self.world.entity(occurrence).data["data"]["holder"]
        return self._turn(self._start_duel(holder, "bout", purpose={"lei_tai": occurrence}))

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        purpose = data.get("purpose") or {}
        entry = self.world.chronicle_entry(data["duel"]) if data.get("duel") else None
        if entry is None or len(entry.actors) < 2:
            return lines
        me, opponent = entry.actors[0], entry.actors[1]
        if "tournament" in purpose:
            events = T.bout_result_events(self.world, purpose["tournament"], purpose["round"], purpose["match"],
                                          me, opponent, data)
            lines += self._commit(events) if events else []
        elif "lei_tai" in purpose:
            won = data.get("result") == "won" and data.get("verdict") != "kill"
            lines += self._commit(T.lei_tai_result_events(self.world, purpose["lei_tai"], me, opponent, won))
        return lines
