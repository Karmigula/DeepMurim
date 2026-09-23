"""Land in the engine (phase 3c spec 3)."""

import systems.land as land
from engine.actions import Action, Choice
from systems.purse import silver_of


class LandMixin:
    def _faction_options(self, npc) -> list:
        options = super()._faction_options(npc)
        town = self.place.id
        if land.magistrate_of(self.world, town) == npc.id and land.buy_block(self.world, self.player.id, town) is None:
            options.append(Choice(f"Buy land here ({land.land_price(self.world, town)} silver)", Action("buy_land", town)))
        return options

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        fid = land.seizable(self.world, npc.id, self.place.id)
        if fid is not None:
            extras.append(Choice("Seize this seat", Action("seize_seat", fid)))
        return extras

    def _general_extras(self) -> list:
        extras = super()._general_extras()
        if land.is_ruin(self.world, self.place.id):
            extras.append(Choice("Claim the old hall", Action("claim_land", self.place.id)))
        return extras

    def _presence_extras(self) -> list:
        lines = super()._presence_extras()
        town = self.place.id
        if land.owner_of(self.world, town) == self.player.id:
            lines.append(("You own land here.", "dim"))
        elif land.is_ruin(self.world, town):
            lines.append(("An abandoned hall stands at the edge of town.", "dim"))
        return lines

    def _do_buy_land(self, town):
        town = self.place.id
        magistrate = land.magistrate_of(self.world, town)
        if self.focus is None or self.focus != magistrate:
            return self._turn([("Land is registered with the magistrate.", "system")])
        if (why := land.buy_block(self.world, self.player.id, town)) is not None:
            return self._turn([(why, "system")])
        price = land.land_price(self.world, town)
        if silver_of(self.world, self.player.id) < price:
            return self._turn([(f"The land costs {price} silver.", "system")])
        self.submenu = None
        return self._turn(self._commit(land.buy_events(self.world, self.player.id, magistrate, town)))

    def _do_claim_land(self, town):
        town = self.place.id
        if not land.is_ruin(self.world, town):
            return self._turn([("There is nothing here to claim.", "system")])
        rival = land.contester(self.world, town)
        if rival is None:
            return self._turn(self._commit(land.claim_events(self.player.id, town)))
        self.world.unrelate(rival, "located_in")
        self.world.relate(rival, town, "located_in")
        return self._turn([(f"{self.world.entity(rival).name} contests your claim.", "system")]
                          + self._start_duel(rival, "duel", purpose={"claim": town}))

    def _do_seize_seat(self, faction_id):
        if self.focus is None or land.seizable(self.world, self.focus, self.place.id) != faction_id:
            return self._turn([("There is no seat to seize here.", "system")])
        return self._turn(self._start_duel(self.focus, "duel", purpose={"seize": faction_id}))

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        purpose = data.get("purpose") or {}
        if data["result"] != "won":
            return lines
        if purpose.get("claim") == self.place.id and land.is_ruin(self.world, self.place.id):
            lines += self._commit(land.claim_events(self.player.id, self.place.id))
        elif purpose.get("seize"):
            lines += self._commit(land.seized_events(self.world, self.player.id, purpose["seize"], self.place.id))
        return lines
