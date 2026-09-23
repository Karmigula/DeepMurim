"""Rising in a faction, in the engine (phase 3b spec 5)."""

from engine.actions import Action, Choice
from systems import factions as F
from systems import halls, ranks
from systems.purse import silver_of


class RanksMixin:
    def _my_faction_here(self, faction_id) -> bool:
        found = F.membership(self.world, self.player.id, faction_id)
        return bool(found and found[1].get("status", "member") == "member"
                    and self.focus is not None and faction_id in halls.recruits_for(self.world, self.focus))

    def _role(self, npc_id, faction_id) -> str | None:
        found = F.membership(self.world, npc_id, faction_id)
        return found[1].get("role") if found else None

    def _faction_options(self, npc) -> list:
        options = super()._faction_options(npc)
        me, town = self.player.id, self.place.id
        for fid in halls.recruits_for(self.world, npc.id):
            found = F.membership(self.world, me, fid)
            if not found or found[1].get("status", "member") != "member":
                continue
            role = self._role(npc.id, fid)
            if role in ("elder", "leader"):
                options.append(Choice("Ask for promotion", Action("promote", fid)))
                if ranks.teachable(self.world, me, fid):
                    options.append(Choice("Learn a sect art", Action("learn_sect_art", fid)))
                if role == "elder":
                    options.append(Choice(f"Offer a gift ({ranks.gift_price(self.world, me, fid)} silver)", Action("gift", fid)))
            if halls.keeper_at(self.world, fid, town) == npc.id:
                if ranks.stipend_due(self.world, me, fid):
                    options.append(Choice(f"Collect your stipend ({ranks.stipend_due(self.world, me, fid)} silver)",
                                          Action("stipend", fid)))
                if self.world.entity(fid).data.get("seat") == town and ranks.library_manual(self.world, me, fid):
                    options.append(Choice("Study in the library", Action("library", fid)))
        return options

    def _do_promote(self, faction_id):
        if not self._my_faction_here(faction_id) or self._role(self.focus, faction_id) not in ("elder", "leader"):
            return self._turn([("Only an elder can raise you.", "system")])
        if (why := ranks.promotion_block(self.world, self.player.id, faction_id)) is not None:
            return self._turn([(why, "system")])
        self.submenu = None
        return self._turn(self._commit(ranks.promoted_events(self.world, self.player.id, faction_id, self.focus, self.place.id)))

    def _do_stipend(self, faction_id):
        if not self._my_faction_here(faction_id) or not ranks.stipend_due(self.world, self.player.id, faction_id):
            return self._turn([("Nothing is owed to you yet.", "system")])
        self.submenu = None
        return self._turn(self._commit(ranks.stipend_events(self.world, self.player.id, faction_id, self.focus, self.place.id)))

    def _do_learn_sect_art(self, faction_id):
        arts = ranks.teachable(self.world, self.player.id, faction_id) if self._my_faction_here(faction_id) else []
        if not arts or self._role(self.focus, faction_id) not in ("elder", "leader"):
            return self._turn([("There is nothing they will teach you yet.", "system")])
        self.submenu = None
        return self._turn(self._commit(ranks.taught_events(self.world, self.player.id, self.focus, faction_id,
                                                           self.place.id, arts[0])))

    def _do_library(self, faction_id):
        manual = ranks.library_manual(self.world, self.player.id, faction_id) if self._my_faction_here(faction_id) else None
        if manual is None or self.world.entity(faction_id).data.get("seat") != self.place.id:
            return self._turn([("The library has nothing for you.", "system")])
        self.submenu = None
        return self._turn(self._commit(ranks.library_events(self.world, self.player.id, faction_id, self.place.id, manual)))

    def _do_gift(self, faction_id):
        if not self._my_faction_here(faction_id) or self._role(self.focus, faction_id) != "elder":
            return self._turn([("Gifts go to an elder.", "system")])
        price = ranks.gift_price(self.world, self.player.id, faction_id)
        if silver_of(self.world, self.player.id) < price:
            return self._turn([(f"You don't have {price} silver.", "system")])
        return self._turn(self._commit(ranks.gift_events(self.world, self.player.id, self.focus, faction_id, self.place.id)))
