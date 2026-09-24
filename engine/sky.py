"""The sky in the engine (phase 4d spec 7): the player's tribulation and the beast hunt.

Tasks 4 and 6 add the treasure race, the sky and rankings pages, and what arrival shows.
"""

import systems.events.beast_tide as beast_tide
import systems.events.tribulation as tribulation
import systems.races as races
import systems.rankings as rankings
import systems.sky as sky
import systems.world_events as W
from engine.rankings_page import rankings_lines
from narrate import sky_text
from narrate.gossip_text import rumour_text
from narrate.outcomes import cap
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
        if W.showing(self.world, self.place.id):
            extras.append(Choice("Look at the sky", Action("sky")))
        if rankings.latest(self.world, self.player.id) is not None:
            extras.append(Choice("The Pavilion's lists", Action("rankings")))
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

    # --- what the player sees of the sky, and the lists (phase 4d spec 7) ----------------------
    def _before_scene(self) -> None:
        super()._before_scene()
        sky.observe(self.world, self.place.id)
        rankings.post_in_city(self.world, self.player.id, self.place.id)

    def _sky_news(self) -> list:
        """A line for each occurrence over this place whose stage the player has not yet seen."""
        world, me, town = self.world, self.player.id, self.place.id
        before = dict(self.player.data.get("sky_seen", {}))
        seen, lines = dict(before), []
        for row in W.showing(world, town):
            data = world.entity(row[W.ID]).data
            stage = W.stage_at(data, world.time)
            if stage in sky_text.STAGE_WORDS and seen.get(str(row[W.ID])) != stage:
                seen[str(row[W.ID])] = stage
                lines.append((sky_text.stage_line(world, data, stage, town), "dim"))
        live = {str(row[W.ID]) for row in W.index(world) if not row[W.DONE]}
        seen = {k: v for k, v in seen.items() if k in live}
        if seen != before:
            world.update_data(me, sky_seen=seen)
        return lines

    def _after_arrival(self) -> list:
        return super()._after_arrival() + self._sky_news()

    def _after_look(self) -> list:
        return super()._after_look() + self._sky_news()

    def _do_sky(self, _target):
        world, me, town = self.world, self.player.id, self.place.id
        overhead = sky_text.sky_facts(world, town)
        lines = [("The sky", "heading")]
        lines += [(f"  {t}", "dim") for t in overhead] or [("  Clear. Nothing strange hangs over this place.", "dim")]
        here = {row[W.ID] for row in W.showing(world, town)}
        newest: dict = {}
        for belief, fact in world.known_facts(me):
            occurrence = fact.data.get("occurrence")
            if fact.predicate == "phenomenon" and occurrence not in here and fact.data.get("until", 0) > world.time \
                    and (occurrence not in newest or fact.time >= newest[occurrence][1].time):
                newest[occurrence] = (belief, fact)
        if newest:
            lines.append(("Heard of elsewhere:", "heading"))
            for belief, fact in newest.values():
                days = max(1, (fact.data["until"] - world.time + 3) // 4)
                lines.append((f"  {rumour_text(world, belief.variant, me)} ({days} days left)", "dim"))
        return self._turn(lines)

    def _do_rankings(self, _target):
        return self._turn(rankings_lines(self.world, self.player.id))


def sheet_sky_lines(world, player: int) -> list:
    """The character sheet's heavens: what the sky does to you here, and your place on the lists."""
    here = world.targets(player, "located_in")
    lines = [("", "default"), ("The heavens:", "heading")]
    for row in (W.showing(world, here[0]) if here else []):
        mods = W.TYPES.get(row[W.TYPE], W.DEFAULTS)["modifiers"]
        if mods and W.stage_at(world.entity(row[W.ID]).data, world.time) == "active":
            words = ", ".join(f"{k} x{v:g}" for k, v in sorted(mods.items()))
            lines.append((f"  {cap(sky_text.phenomenon_name(row[W.TYPE]).removeprefix('a '))}: {words}", "default"))
    if len(lines) == 2:
        lines.append(("  quiet", "dim"))
    known = rankings.latest(world, player)
    mine = rankings.rank_of_you(world, known["lists"], player) if known else None
    lines.append((f"Rank: {rankings.title(*mine)} (the lists of year {known['year']})" if mine else "Rank: unranked",
                  "default"))
    return lines
