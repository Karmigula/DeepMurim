"""The market in the engine (phase 4c spec 8): a page, a two-level trade menu, the price book, merchant news."""

import systems.market as market
from engine.actions import Action, Choice
from systems.beliefs import knowledge_of
from systems.goods import GOODS, MULE_PRICE, ORDER, capacity, carried, pack_weight
from systems.rumours import heard_events

MARKET_MENUS = ("market", "trade_good")
AMOUNTS = (1, 5, 10)


class MarketMixin:
    _trade_good: str | None = None

    def _market_lines(self) -> list:
        world, me, town = self.world, self.player.id, self.place.id
        book = market.known_prices(world, me)
        pack = carried(world, me)
        lines = [(f"Market of {self.place.name} (pack {pack_weight(pack)}/{capacity(world, me)})", "heading")]
        for good in ORDER:
            here, sell = market.price(world, town, good), market.sell_price(world, town, good)
            elsewhere = [(entry["prices"][good], t, entry) for t, entry in book.items()
                         if t != town and good in entry["prices"]]
            note = ""
            if elsewhere:
                best, where, entry = max(elsewhere, key=lambda e: (e[0], -e[1]))
                days = max(0, (world.time - entry["time"]) // 4)
                note = f" | {best} in {world.entity(where).name}, {days}d ago"
            lines.append((f"  {good:<6} buy {here:>4}  sell {sell:>4}  carry {pack.get(good, 0):>3}{note}", "dim"))
        return lines

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        if self.focus is None and self.submenu in MARKET_MENUS:
            if self.submenu == "market":
                goods = [Choice(f"Trade {g} ({market.price(self.world, self.place.id, g)})", Action("trade_good", g))
                         for g in ORDER]
                options["market"] = (goods, Action("back"))
            else:
                good = self._trade_good
                trades = [Choice(f"Buy {n} {good}", Action("buy_goods", (good, n))) for n in AMOUNTS] \
                    + [Choice(f"Sell {n} {good}", Action("sell_goods", (good, n))) for n in AMOUNTS]
                options["trade_good"] = (trades, Action("market"))
        return options

    def _general_extras(self) -> list:
        extras = super()._general_extras()
        extras.append(Choice("Visit the market", Action("market")))
        if market.mule_block(self.world, self.player.id) is None:
            extras.append(Choice(f"Buy a mule ({MULE_PRICE} silver)", Action("buy_mule")))
        return extras

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        if npc.data.get("occupation") == "merchant":
            extras.append(Choice("Ask about trade", Action("ask_trade")))
        return extras

    def _status_suffix(self) -> str:
        suffix = super()._status_suffix()
        pack = carried(self.world, self.player.id)
        if not pack:
            return suffix
        return f"{suffix} pack {pack_weight(pack)}/{capacity(self.world, self.player.id)}"

    def _after_duel(self, data: dict) -> list:
        lines = super()._after_duel(data)
        if data.get("by") == "opponent" and data.get("verdict") == "rob" and self.combat is None:
            robber = self.world.entity(self.world.chronicle_entry(data.get("duel")).actors[1]) \
                if self.world.chronicle_entry(data.get("duel")) else None
            if robber is not None:
                lines += self._commit(market.robbery_events(self.world, self.player.id, robber.id,
                                                            self.place.id, data.get("duel")))
        return lines

    def _do_market(self, _target):
        market.record_visit(self.world, self.player.id, self.place.id)
        self.submenu = "market"
        return self._turn(self._market_lines())

    def _do_trade_good(self, good):
        if good not in GOODS:
            return self._turn([("There is no such good.", "system")])
        self._trade_good, self.submenu = good, "trade_good"
        buy, sell = market.price(self.world, self.place.id, good), market.sell_price(self.world, self.place.id, good)
        have = carried(self.world, self.player.id).get(good, 0)
        return self._turn([(f"{good.capitalize()}: buy at {buy}, sell at {sell}. You carry {have}.", "system")])

    def _trade(self, target, block, build):
        if not isinstance(target, (tuple, list)) or len(target) != 2:
            return self._turn([("There is no such trade.", "system")])
        good, n = target
        why = block(self.world, self.player.id, self.place.id, good, n)
        self._trade_good, self.submenu = good, "trade_good"
        if why is not None:
            return self._turn([(why, "system")])
        lines = self._commit(build(self.world, self.player.id, self.place.id, good, n))
        market.record_visit(self.world, self.player.id, self.place.id)
        self.submenu = "trade_good"
        return self._turn(lines)

    def _do_buy_goods(self, target):
        return self._trade(target, market.buy_block, market.buy_events)

    def _do_sell_goods(self, target):
        return self._trade(target, market.sell_block, market.sell_events)

    def _do_buy_mule(self, _target):
        if (why := market.mule_block(self.world, self.player.id)) is not None:
            return self._turn([(why, "system")])
        return self._turn(self._commit(market.mule_events(self.world, self.player.id, self.place.id)))

    def _do_prices(self, _target):
        world, me = self.world, self.player.id
        book = market.known_prices(world, me)
        lines = [("Your price book", "heading")]
        if not book:
            return self._turn(lines + [("  You have seen no markets and heard no talk of trade.", "dim")])
        for good in ORDER:
            seen = [(entry["prices"][good], t, entry) for t, entry in book.items() if good in entry["prices"]]
            if not seen:
                continue
            low, high = min(seen, key=lambda e: (e[0], e[1])), max(seen, key=lambda e: (e[0], -e[1]))

            def where(e):
                how = "seen" if e[2]["source"] == "visit" else "heard"
                return f"{e[0]} in {world.entity(e[1]).name} ({how} {max(0, (world.time - e[2]['time']) // 4)}d ago)"
            lines.append((f"  {good:<6} cheapest {where(low)}; dearest {where(high)}", "dim"))
        return self._turn(lines)

    def _do_ask_trade(self, _target):
        npc = self.focus
        if npc is None or self.world.entity(npc).data.get("occupation") != "merchant":
            return self._turn([("Ask a merchant.", "system")])
        mine = {b.fact_id for b in self.world.beliefs(self.player.id)}
        news = [(b, f) for b, f in knowledge_of(self.world, npc)
                if f.predicate in ("shortage", "glut") and f.id not in mine]
        if not news:
            return self._turn([("They know of no trade worth telling.", "system")])
        belief, fact = max(news, key=lambda p: (p[1].weight, p[1].time, p[1].id))
        return self._turn(self._commit(heard_events(self.world, self.player.id, npc, self.place.id, belief, fact)))
