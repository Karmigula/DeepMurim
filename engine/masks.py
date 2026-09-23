"""Masks in the engine (phase 3a spec 8): buying, wearing, removing, and being recognised."""

from dataclasses import replace

import systems.learning as learning
import systems.masks as masks
from engine.actions import Action, Choice
from systems.purse import silver_of


class MasksMixin:
    def _stamp(self, events: list) -> list:
        events = super()._stamp(events)
        persona = masks.worn_persona(self.world, self.player.id)
        if not persona:
            return events
        me = self.player.id
        return [replace(e, data={**e.data, "as": persona})
                if e.actors and e.actors[0] == me and e.kind not in masks.UNSTAMPED and "as" not in e.data else e
                for e in events]

    def _after_commit(self, ids: list, events: list) -> list:
        lines = super()._after_commit(ids, events)
        found = masks.recognition_events(self.world, self.player.id, ids, events)
        return lines + (self._commit(found) if found else [])

    def _status_suffix(self) -> str:
        return super()._status_suffix() + (" (masked)" if masks.worn_persona(self.world, self.player.id) else "")

    def _general_extras(self) -> list:
        extras = super()._general_extras()
        me, place = self.player.id, self.place.id
        persona = masks.worn_persona(self.world, me)
        if persona:
            n = len(masks.onlookers(self.world, me, place, persona, False))
            extras.append(Choice("Remove your mask" + (f" ({n} here would know you)" if n else ""), Action("remove_mask")))
        elif owned := masks.masks_of(self.world, me):
            n = len(masks.onlookers(self.world, me, place, owned[0].data.get("persona"), True))
            extras.append(Choice("Wear your mask" + (f" ({n} here know your face)" if n else ""), Action("wear_mask")))
        return extras

    def _goods_choices(self) -> list:
        choices = super()._goods_choices()
        if self.world.entity(self.focus).data.get("occupation") == "merchant":
            choices.append(Choice(f"Buy a mask ({masks.MASK_PRICE} silver)", Action("buy_mask")))
        return choices

    def _do_buy_mask(self, _target):
        if self.focus is None or self.world.entity(self.focus).data.get("occupation") != "merchant" \
                or not learning.will_deal(self.world, self.focus, self.player.id):
            return self._turn([("No one here sells masks.", "system")])
        if silver_of(self.world, self.player.id) < masks.MASK_PRICE:
            return self._turn([("You cannot afford it.", "system")])
        return self._turn(self._commit(masks.buy_mask_events(self.player.id, self.focus, self.place.id)))

    def _do_wear_mask(self, _target):
        if busy := self._busy():
            return busy
        me = self.player.id
        if masks.worn_persona(self.world, me):
            return self._turn([("You are already masked.", "system")])
        owned = masks.masks_of(self.world, me)
        if not owned:
            return self._turn([("You have no mask.", "system")])
        return self._turn(self._commit(masks.wear_events(self.world, me, self.place.id, owned[0].id)))

    def _do_remove_mask(self, _target):
        if busy := self._busy():
            return busy
        if not masks.worn_persona(self.world, self.player.id):
            return self._turn([("You are not wearing a mask.", "system")])
        return self._turn(self._commit(masks.remove_events(self.world, self.player.id, self.place.id)))
