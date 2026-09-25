"""The lei tai (phase 4e spec 3): a platform in town for an afternoon; whoever holds it at dusk takes the purse.

The afternoon's challengers settle it among themselves when the day begins (plan ruling 4); the
player may then challenge the holder once (engine/tournament.py).
"""

import systems.lives as lives
import systems.tournaments as T
from systems.facts import make_variant, place_name, record_fact
from systems.purse import silver_of
from world.events import Event, effect, listen
from world.gen.materialize import people_at

MIN_FIGHTERS = 2
MAX_CHALLENGERS = 5


def _fighters(world, town: int) -> list[int]:
    return sorted(p.id for p in people_at(world, town)
                  if lives.simulated(p) and T.realm_of(world, p.id) >= 1)[:MAX_CHALLENGERS]


def eligible(world, town: int, n: int) -> bool:
    """A platform goes up only in the player's region: a local afternoon nobody far away hears of (ruling 10)."""
    import systems.world_events as W
    player = world.get_meta("player_id")
    here = world.targets(player, "located_in") if player is not None else []
    if not here or W.place_xy(world, here[0]) != W.place_xy(world, town):
        return False
    return len(_fighters(world, town)) >= MIN_FIGHTERS


def start_data(world, town: int, n: int, rng) -> dict:
    return {"kind": "lei_tai", "holder": None, "challengers": [], "results": [], "purse": rng.randint(20, 60),
            "paid": False, "challenged": []}


def qualifies(world, occurrence, person: int, slack: int = 0) -> bool:
    return True


def on_stage(world, occurrence, stage: str) -> list[Event]:
    t = occurrence.data["data"]
    if stage == "active":
        fighters = [p for p in _fighters(world, occurrence.data["place"])]
        holder, results = (fighters[0] if fighters else None), []
        for i, challenger in enumerate(fighters[1:]):
            winner = T._sim_winner(world, occurrence, holder, challenger, 0, i)
            results.append([holder, challenger, winner])
            holder = winner
        return [Event("lei_tai_settled", (), occurrence.data["place"],
                      {"occurrence": occurrence.id, "holder": holder, "challengers": fighters, "results": results})]
    if stage == "over" and t["holder"] is not None and not t["paid"] and T.alive(world, t["holder"]):
        return [Event("lei_tai_held", (t["holder"],), occurrence.data["place"],
                      {"occurrence": occurrence.id, "purse": t["purse"]})]
    return []


@effect("lei_tai_settled")
def _settled(world, event) -> None:
    d = event.data
    occurrence = world.entity(d["occurrence"])
    world.update_data(occurrence.id, data={**occurrence.data["data"], "holder": d["holder"],
                                           "challengers": d["challengers"], "results": d["results"]})


@effect("lei_tai_held")
def _held(world, event) -> None:
    holder, d = event.actors[0], event.data
    world.update_data(holder, silver=silver_of(world, holder) + d["purse"])
    occurrence = world.entity(d["occurrence"])
    world.update_data(occurrence.id, data={**occurrence.data["data"], "paid": True})


@listen("lei_tai_held")
def _held_news(world, event, event_id: int) -> None:
    holder = event.actors[0]
    variant = make_variant("held_lei_tai", holder, None, place=place_name(world, event.place))
    variant["kind"] = "lei_tai"
    record_fact(world, holder, "held_lei_tai", None, place=event.place, source_event=event_id, weight=0.75,
                variant=variant)
