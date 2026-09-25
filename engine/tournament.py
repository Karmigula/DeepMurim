"""Tournaments in the engine (phase 4e spec 6): register, answer the herald, fight your bouts, hold the lei tai."""

import systems.arena as arena
import systems.intrigue as intrigue
import systems.tournaments as T
import systems.wagers as wagers
import systems.world_events as W
from engine.actions import Action, Choice
from engine.tournament_page import bracket_lines, known, tournaments_lines
from narrate.tournament_text import KIND_NAMES, stage_line


class TournamentMixin:
    def _general_extras(self) -> list:
        extras = super()._general_extras()
        world, me, town = self.world, self.player.id, self.place.id
        for open_ in T.all_here(world, town, T.KINDS, ("announced",)):
            if T.register_block(world, open_, me) is None:
                kind = world.entity(open_).data["type"]
                extras.append(Choice(f"Enter {KIND_NAMES[kind]}", Action("register", open_)))
                if T.can_preside(world, open_, me):
                    extras.append(Choice("Preside over the contest", Action("preside", open_)))
        call = T.player_call(world, me, town)
        if call is not None:
            name = world.entity(call[3]).name
            extras.append(Choice(f"Answer the herald: fight {name}", Action("bout", call[0])))
            extras.append(Choice("Forfeit your bout", Action("forfeit_bout", call[0])))
        fighting = T.fighting_here(world, town)

        def at(oid):  # two tournaments in one city: say which
            return f" at {KIND_NAMES[world.entity(oid).data['type']]}" if len(fighting) > 1 else ""
        for watching in fighting:
            if arena.watchable(world, watching, me) is not None:
                extras.append(Choice(f"Watch today's bouts{at(watching)}", Action("watch", watching)))
        for faction, elder in sorted((int(f), e) for f, e in self.player.data.get("invitations", {}).items()):
            if world.entity(elder) is not None and town in world.targets(elder, "located_in"):
                extras.append(Choice(f"Accept the invitation of the {world.entity(faction).name}",
                                     Action("accept_invitation", faction)))
        for betting in fighting:
            if wagers.open_matches(world, betting) and wagers.stake_limit(world, me) >= 1:
                extras.append(Choice(f"Visit the bookmaker{at(betting)}", Action("bookmaker", betting)))
        honour = T.honourable(world, me, town)
        if honour is not None:
            name = world.entity(honour[1]).name
            if T.honour_block(world, me, honour[1], "reward") is None:
                extras.append(Choice(f"Reward {name}, the champion ({T.CHAMPION_REWARD} silver)",
                                     Action("reward_champion", honour[0])))
            if T.honour_block(world, me, honour[1], "disciple") is None:
                extras.append(Choice(f"Take {name}, the champion, as your disciple", Action("take_champion", honour[0])))
        platform = T.here(world, town, ("lei_tai",), ("active",))
        if platform is not None and T.lei_tai_open(world, platform, me):
            holder = world.entity(platform).data["data"]["holder"]
            extras.append(Choice(f"Challenge the platform holder, {world.entity(holder).name}",
                                 Action("challenge_lei_tai", platform)))
        for raided in fighting:
            if intrigue.defence_open(world, raided, me) is not None:
                extras.append(Choice("Join the defence against the cultists", Action("defend", raided)))
        for occurrence in intrigue.exposable(world, me):
            fix = intrigue.fix_of(world, occurrence)
            extras.append(Choice(f"Expose the fix: {world.entity(fix['victim']).name} was {fix['how']}",
                                 Action("expose_fix", occurrence)))
        return extras

    def _herald(self) -> list:
        lines = []
        active = T.here(self.world, self.place.id, T.KINDS, ("active",))
        if active is not None and intrigue.defence_open(self.world, active, self.player.id) is not None:
            lines.append(("Black-robed cultists storm the platform before the final; the crowd scatters.", "red"))
        call = T.player_call(self.world, self.player.id, self.place.id)
        if call is None:
            return lines
        kind = self.world.entity(call[0]).data["type"]
        return lines + [(f"The herald calls your name: today you fight {self.world.entity(call[3]).name} "
                         f"at {KIND_NAMES[kind]}.", "dim")]

    def _tournament_news(self) -> list:
        """A line for each tournament here at a stage the player has not yet seen: heralds, the opening day."""
        world, town = self.world, self.place.id
        before = dict(self.player.data.get("tour_seen", {}))
        seen, lines = dict(before), []
        for row in W.index(world):
            if row[W.PLACE] != town or row[W.DONE] or row[W.TYPE] not in T.KINDS + ("lei_tai",):
                continue
            occurrence = world.entity(row[W.ID])
            stage = W.stage_at(occurrence.data, world.time)
            if stage in ("announced", "active") and seen.get(str(row[W.ID])) != stage:
                seen[str(row[W.ID])] = stage
                lines.append((stage_line(world, occurrence, stage), "dim"))
        live = {str(row[W.ID]) for row in W.index(world) if not row[W.DONE]}
        seen = {k: v for k, v in seen.items() if k in live}
        if seen != before:
            world.update_data(self.player.id, tour_seen=seen)
        return lines

    def _after_look(self) -> list:
        return super()._after_look() + self._tournament_news() + self._herald()

    def _after_arrival(self) -> list:
        return super()._after_arrival() + self._tournament_news() + self._herald()

    def _do_register(self, occurrence):
        if occurrence is None:  # typed: the tournament taking names here
            occurrence = T.here(self.world, self.place.id, T.KINDS, ("announced",))
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
        elif "raid" in purpose and self.world.entity(purpose["raid"]).kind == "world_event":  # not a 3b duty's raid
            won = data.get("result") == "won"
            lines += self._commit(intrigue.defended_events(self.world, purpose["raid"], me, opponent, won))
        elif "lei_tai" in purpose:
            won = data.get("result") == "won" and data.get("verdict") != "kill"
            lines += self._commit(T.lei_tai_result_events(self.world, purpose["lei_tai"], me, opponent, won))
        return lines

    # --- the bookmaker (phase 4e spec 5.1) ----------------------------------------------------
    _betting_on: int | None = None

    def _board(self, occurrence: int) -> tuple[list, list]:
        world, me = self.world, self.player.id
        stake = wagers.stake_limit(world, me)
        lines, choices = [(f"The odds board (you may stake up to {stake} silver):", "heading")], []
        for r, i, m in wagers.open_matches(world, occurrence)[:4]:
            prices = wagers.odds(world, occurrence, r, i)
            a, b = world.entity(m["a"]).name, world.entity(m["b"]).name
            lines.append((f"  Round {r + 1}: {a} at {prices[m['a']]:.2f} to 1, {b} at {prices[m['b']]:.2f} to 1", "dim"))
            choices += [Choice(f"Bet {stake} on {a}", Action("bet", (occurrence, r, i, m["a"]))),
                        Choice(f"Bet {stake} on {b}", Action("bet", (occurrence, r, i, m["b"])))]
        if intrigue.ask_block(world, occurrence, me) is None:
            choices.append(Choice("Ask what the bookmaker has heard", Action("ask_bookmaker", occurrence)))
        return lines, choices

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        if self.focus is None and self.submenu == "wagers" and self._betting_on is not None:
            options["wagers"] = (self._board(self._betting_on)[1], Action("back"))
        if self.focus is None and self.submenu == "tournaments":
            options["tournaments"] = ([Choice(f"The bracket in {self.world.entity(self.world.entity(oid).data['place']).name}",
                                              Action("bracket", oid)) for oid in known(self.world, self.player.id)],
                                      Action("back"))
        return options

    def _do_bookmaker(self, occurrence):
        if not isinstance(occurrence, int) or occurrence not in T.fighting_here(self.world, self.place.id):
            return self._turn([("There is no bookmaker taking bets here.", "system")])
        self._betting_on, self.submenu = occurrence, "wagers"
        return self._turn(self._board(occurrence)[0])

    def _do_bet(self, target):
        if not isinstance(target, (tuple, list)) or len(target) != 4:
            return self._turn([("Bet on whom?", "system")])
        occurrence, r, i, on = target
        stake = wagers.stake_limit(self.world, self.player.id)
        why = wagers.bet_block(self.world, occurrence, r, i, on, stake, self.player.id)
        if why:
            return self._turn([(why, "system")])
        lines = self._commit(wagers.bet_events(self.world, occurrence, r, i, on, stake, self.player.id))
        self._betting_on, self.submenu = occurrence, "wagers"
        return self._turn(lines)

    # --- watching and invitations (phase 4e spec 5.2) ------------------------------------------
    def _do_watch(self, occurrence):
        if occurrence is None:  # typed: today's bouts here
            occurrence = next((o for o in T.fighting_here(self.world, self.place.id)
                               if arena.watchable(self.world, o, self.player.id) is not None), None)
        events = arena.watch_events(self.world, occurrence, self.player.id) if isinstance(occurrence, int) else []
        if not events:
            return self._turn([("There is no bout to watch here now.", "system")])
        return self._turn(self._commit(events))

    def _do_accept_invitation(self, faction):
        from systems.membership import joined_events, refusal
        invitations = dict(self.player.data.get("invitations", {}))
        elder = invitations.get(str(faction))
        if elder is None:
            return self._turn([("No one has invited you.", "system")])
        del invitations[str(faction)]
        self.world.update_data(self.player.id, invitations=invitations)
        why = refusal(self.world, self.player.id, faction, self.place.id)  # no trial, but every other rule of joining
        if why:
            return self._turn([(why, "system")])
        return self._turn(self._commit(joined_events(self.world, self.player.id, elder, faction, self.place.id, False)))

    # --- dark interventions (phase 4e spec 5.4) ----------------------------------------------------
    def _do_defend(self, occurrence):
        cultist = intrigue.defence_open(self.world, occurrence, self.player.id) if isinstance(occurrence, int) else None
        if cultist is None:
            return self._turn([("There is no fighting here to join.", "system")])
        return self._turn(self._start_duel(cultist, "duel", purpose={"raid": occurrence}))

    def _do_expose_fix(self, occurrence):
        events = intrigue.expose_events(self.world, occurrence, self.player.id, self.place.id) \
            if isinstance(occurrence, int) else []
        if not events:
            return self._turn([("You know of no fix to expose.", "system")])
        return self._turn(self._commit(events))

    def _do_ask_bookmaker(self, occurrence):
        why = intrigue.ask_block(self.world, occurrence, self.player.id) if isinstance(occurrence, int) \
            else "There is no bookmaker here."
        if why:
            return self._turn([(why, "system")])
        lines = self._commit(intrigue.ask_events(self.world, occurrence, self.player.id))
        self._betting_on, self.submenu = occurrence, "wagers"
        return self._turn(lines)

    # --- the pages (phase 4e spec 6) ---------------------------------------------------------------
    def _do_tournaments(self, _target):
        self.submenu = "tournaments"
        return self._turn(tournaments_lines(self.world, self.player.id))

    def _do_bracket(self, occurrence):
        found = known(self.world, self.player.id)
        if occurrence is None:  # typed: the one here, else the one you are in, else the newest you know of
            here = [oid for oid in found if self.world.entity(oid).data["place"] == self.place.id]
            mine = [oid for oid in found if self.player.id in self.world.entity(oid).data["data"].get("entrants", [])]
            occurrence = (here or mine or found or [None])[-1]
        if occurrence not in found:
            return self._turn([("You know of no such tournament.", "system")])
        return self._turn(bracket_lines(self.world, self.player.id, occurrence))

    def _do_odds(self, _target):
        occurrence = next(iter(T.fighting_here(self.world, self.place.id)), None)
        if occurrence is None:
            return self._turn([("No bookmaker takes bets here.", "system")])
        return self._do_bookmaker(occurrence)

    def _do_bet_on(self, target):
        world, me = self.world, self.player.id
        occurrence = next(iter(T.fighting_here(world, self.place.id)), None)
        if occurrence is None or not isinstance(target, tuple) or len(target) != 2:
            return self._turn([("No bookmaker takes bets here.", "system")])
        name, stake = target
        words = str(name).lower().split()
        found = [(r, i, p) for r, i, m in wagers.open_matches(world, occurrence) for p in (m["a"], m["b"])
                 if words and all(any(part.startswith(w) for part in world.entity(p).name.lower().split()) for w in words)]
        if len(found) != 1:
            return self._turn([("Bet on whom? Name one fighter on the odds board.", "system")])
        r, i, on = found[0]
        why = wagers.bet_block(world, occurrence, r, i, on, stake, me)
        if why:
            return self._turn([(why, "system")])
        return self._turn(self._commit(wagers.bet_events(world, occurrence, r, i, on, stake, me)))

    # --- presiding: honouring the champion (phase 4e spec 3) ------------------------------------
    def _honour(self, occurrence, how: str):
        found = T.honourable(self.world, self.player.id, self.place.id)
        if found is None or found[0] != occurrence:
            return self._turn([("There is no champion of yours to honour here.", "system")])
        why = T.honour_block(self.world, self.player.id, found[1], how)
        if why:
            return self._turn([(why, "system")])
        return self._turn(self._commit(T.honour_events(self.world, occurrence, self.player.id, found[1], how)))

    def _do_reward_champion(self, occurrence):
        return self._honour(occurrence, "reward")

    def _do_take_champion(self, occurrence):
        return self._honour(occurrence, "disciple")
