"""Betting (phase 4e spec 5.1): the host town's bookmaker prices each match from what the town believes.

Bets open when the bracket is drawn (plan ruling 3) and settle when the match does: a walkover or a
forfeit is a result like any other; a disqualification voids the match's bets; a bettor's death voids
theirs and refunds the stake to their estate. Betting on your own opponent and losing is a scandal.
"""

import systems.tournaments as T
import systems.world_events as W
from systems.facts import make_variant, place_name, record_fact
from systems.purse import silver_of
from world.events import Event, commit, effect, listen

MARGIN = 0.10
MAX_SHARE = 0.10
P_BOUNDS = (0.05, 0.95)  # no bookmaker prices a bout as a certainty, however famous one side is
MIN_ODDS = 1.05  # a winning bet returns more than its stake


def open_matches(world, occurrence_id: int) -> list[tuple[int, int, dict]]:
    """Matches one can bet on: both fighters known and still here to fight, not yet settled."""
    t = world.entity(occurrence_id).data["data"]
    return [(r, i, m) for r, ms in enumerate(t["rounds"]) for i, m in enumerate(ms)
            if m["how"] is None and T.alive(world, m["a"]) and T.alive(world, m["b"])]


def odds(world, occurrence_id: int, r: int, i: int) -> dict[int, float]:
    """Decimal odds for each fighter, from the town's belief in them, less the bookmaker's margin."""
    occurrence = world.entity(occurrence_id)
    m = occurrence.data["data"]["rounds"][r][i]
    s = T.strengths(world, occurrence.data["place"], [m["a"], m["b"]])
    a, b = 1 + max(0.0, s[m["a"]]), 1 + max(0.0, s[m["b"]])
    p = min(P_BOUNDS[1], max(P_BOUNDS[0], a / (a + b)))
    return {m["a"]: round(max(MIN_ODDS, (1 - MARGIN) / p), 2), m["b"]: round(max(MIN_ODDS, (1 - MARGIN) / (1 - p)), 2)}


def stake_limit(world, player: int) -> int:
    return int(silver_of(world, player) * MAX_SHARE)


def bet_block(world, occurrence_id: int, r: int, i: int, on: int, stake: int, player: int) -> str | None:
    occurrence = world.entity(occurrence_id)
    if occurrence.data["place"] not in world.targets(player, "located_in"):
        return "The bookmaker is in the host town."
    if (r, i) not in {(rr, ii) for rr, ii, _ in open_matches(world, occurrence_id)}:
        return "That match is not open for bets."
    m = occurrence.data["data"]["rounds"][r][i]
    if on not in (m["a"], m["b"]):
        return "That fighter is not in the match."
    if stake < 1:
        return "Bet at least one silver."
    if stake > stake_limit(world, player):
        return f"The bookmaker takes no more than a tenth of your silver ({stake_limit(world, player)})."
    return None


def bet_events(world, occurrence_id: int, r: int, i: int, on: int, stake: int, player: int) -> list[Event]:
    return [Event("bet_placed", (player,), world.entity(occurrence_id).data["place"],
                  {"occurrence": occurrence_id, "round": r, "match": i, "on": on, "stake": stake,
                   "odds": odds(world, occurrence_id, r, i)[on], "silver": silver_of(world, player)})]


@effect("bet_placed")
def _placed(world, event) -> None:
    player, d = event.actors[0], event.data
    occurrence = world.entity(d["occurrence"])
    bet = {"player": player, "round": d["round"], "match": d["match"], "on": d["on"], "stake": d["stake"],
           "odds": d["odds"], "silver": d["silver"], "settled": False, "payout": 0}
    world.update_data(occurrence.id, data={**occurrence.data["data"],
                                           "bets": occurrence.data["data"].get("bets", []) + [bet]})
    world.update_data(player, silver=silver_of(world, player) - d["stake"])


@listen("match_resolved")
def _settle(world, event, event_id: int) -> None:
    d = event.data
    t = world.entity(d["occurrence"]).data["data"]
    events = []
    for n, bet in enumerate(t.get("bets", [])):
        if bet["settled"] or (bet["round"], bet["match"]) != (d["round"], d["match"]):
            continue
        void = d["how"] in ("disqualified", "void")
        payout = bet["stake"] if void else int(bet["stake"] * bet["odds"]) if bet["on"] == d["winner"] else 0
        events.append(Event("bet_settled", (bet["player"],), event.place,
                            {"occurrence": d["occurrence"], "bet": n, "payout": payout, "void": void}))
        if not void and bet["player"] == d["loser"] and bet["on"] == d["winner"]:
            variant = make_variant("fixed", bet["player"], None, place=place_name(world, event.place))
            record_fact(world, bet["player"], "fixed", None, place=event.place, source_event=event_id, weight=1.5,
                        variant=variant)
    if events:
        commit(world, events)


@listen("died")
def _void_the_dead(world, event, event_id: int) -> None:
    dead = event.actors[-1]
    events = []
    for row in W.index(world):
        if row[W.TYPE] not in T.KINDS or row[W.DONE]:
            continue
        t = world.entity(row[W.ID]).data["data"]
        for n, bet in enumerate(t.get("bets", [])):
            if bet["player"] == dead and not bet["settled"]:
                events.append(Event("bet_settled", (dead,), event.place,
                                    {"occurrence": row[W.ID], "bet": n, "payout": bet["stake"], "void": True}))
    if events:
        commit(world, events)


@effect("bet_settled")
def _settled(world, event) -> None:
    bettor, d = event.actors[0], event.data
    occurrence = world.entity(d["occurrence"])
    bets = [dict(b) for b in occurrence.data["data"]["bets"]]
    if bets[d["bet"]]["settled"]:
        raise ValueError(f"bet {d['bet']} of tournament #{occurrence.id} is already settled")
    bets[d["bet"]].update(settled=True, payout=d["payout"])
    world.update_data(occurrence.id, data={**occurrence.data["data"], "bets": bets})
    if d["payout"]:
        world.update_data(bettor, silver=silver_of(world, bettor) + d["payout"])
