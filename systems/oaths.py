"""Oaths sworn on the dao heart (phase 5e spec 5): vengeance, protection and abstinence, kept or broken.

An oath is `{kind, whom, until, sworn_at}` in the heart's `oaths`, at most three open. Deaths decide most of them
(a listener); the season settles the rest when their time runs out. Swearing, keeping and breaking are facts that
spread, and a broken oath is dishonour in the towns' eyes (2c's path values).
"""

import systems.demons as D
import systems.heart as HT
import systems.lives as lives
import systems.reputation as reputation
import systems.world_clock as world_clock
from systems.facts import make_variant, place_name, record_fact
from world.events import Event, commit, effect, listen

KINDS = {"vengeance": 3 * 4 * lives.SEASON, "protection": 4 * lives.SEASON, "abstinence": lives.SEASON}
MAX_OPEN = 3
SWORN_STEADY, KEPT_STEADY, BROKEN_STEADY = 5.0, 15.0, -30.0
KEPT_LEAN = {"protection": 10.0}
BROKEN_GUILT = 3
reputation.PATH_VALUE.update({"oath_broken": -0.6, "oath_kept": 0.4})


def oaths(world, person: int) -> list[dict]:
    return list(HT.heart_of(world, person)["oaths"])


def grudges(world, person: int) -> list[int]:
    return [d["whom"] for d in D.demons(world, person) if d["kind"] == "grudge" and isinstance(d["whom"], int)]


def swear_block(world, person: int, kind: str, whom) -> str | None:
    if kind not in KINDS:
        return "There is no such oath."
    open_ = oaths(world, person)
    if len(open_) >= MAX_OPEN:
        return "Three oaths already weigh on your heart."
    if any(o["kind"] == kind and o["whom"] == whom for o in open_):
        return "You have sworn that already."
    if kind == "abstinence":
        return None if whom is None else "Abstinence is sworn for no one."
    target = world.entity(whom) if isinstance(whom, int) else None
    if target is None or target.kind != "person" or target.data.get("dead") or whom == person:
        return "There is no one living to swear it for."
    if kind == "vengeance" and whom not in grudges(world, person):
        return "You bear them no grudge to avenge."
    return None


def swear_events(world, person: int, kind: str, whom, place) -> list[Event]:
    return [Event("oath_sworn", (person,) + ((whom,) if whom is not None else ()), place,
                  {"kind": kind, "whom": whom, "until": world.time + KINDS[kind]})]


@effect("oath_sworn")
def _sworn(world, event) -> None:
    person, d = event.actors[0], event.data
    HT.write(world, person, oaths=oaths(world, person) + [{"kind": d["kind"], "whom": d["whom"], "until": d["until"],
                                                           "sworn_at": world.time}])
    HT.shift_steady(world, person, SWORN_STEADY)


def _end(world, person: int, oath: dict, kept: bool, place) -> Event:
    return Event("oath_kept" if kept else "oath_broken", (person,) + ((oath["whom"],) if oath["whom"] else ()),
                 place, {"kind": oath["kind"], "whom": oath["whom"], "sworn_at": oath["sworn_at"]})


def _close(world, event) -> None:
    person, d = event.actors[0], event.data
    HT.write(world, person, oaths=[o for o in oaths(world, person)
                                   if not (o["kind"] == d["kind"] and o["whom"] == d["whom"])])


@effect("oath_kept")
def _kept(world, event) -> None:
    person = event.actors[0]
    _close(world, event)
    HT.shift_steady(world, person, KEPT_STEADY)
    if event.data["kind"] in KEPT_LEAN:
        HT.write(world, person, lean=min(HT.LEAN_BOUND, HT.lean(world, person) + KEPT_LEAN[event.data["kind"]]))


@effect("oath_broken")
def _broken(world, event) -> None:
    person = event.actors[0]
    _close(world, event)
    HT.shift_steady(world, person, BROKEN_STEADY)
    D.add_demon(world, person, "guilt", event.data["whom"], BROKEN_GUILT)


@listen("died")
def _decided_by_death(world, event, event_id: int) -> None:
    """Vengeance done by any hand; a protected one slain; an abstinent hand that kills."""
    killer, victim = event.actors[0], event.actors[-1]
    player = world.get_meta("player_id")
    if player is None or player == victim or world.entity(player) is None:
        return
    ends = []
    for oath in oaths(world, player):
        if oath["kind"] == "vengeance" and oath["whom"] == victim:
            ends.append(_end(world, player, oath, True, event.place))
        elif oath["kind"] == "protection" and oath["whom"] == victim and killer != victim:
            ends.append(_end(world, player, oath, False, event.place))
        elif oath["kind"] == "abstinence" and killer == player:
            ends.append(_end(world, player, oath, False, event.place))
    commit(world, ends)


def season_hook(world, n: int) -> list[Event]:
    """Oaths whose time has run out: vengeance undone is broken, protection and abstinence kept."""
    player = world.get_meta("player_id")
    if player is None or world.entity(player) is None or not world.entity(player).data.get("heart"):
        return []
    here = next(iter(world.targets(player, "located_in")), None)
    return [_end(world, player, o, o["kind"] != "vengeance", here) for o in oaths(world, player)
            if o["until"] <= world.time]


world_clock.SEASON_HOOKS.append(season_hook)


# --- the news -----------------------------------------------------------------------------------------------------

@listen("oath_sworn")
@listen("oath_kept")
@listen("oath_broken")
def _news(world, event, event_id: int) -> None:
    person, d = event.actors[0], event.data
    variant = make_variant(event.kind, person, d["whom"], place=place_name(world, event.place))
    variant["oath"] = d["kind"]
    record_fact(world, person, event.kind, d["whom"], place=event.place, source_event=event_id,
                weight=1.5 if event.kind == "oath_broken" else 1.0, variant=variant)
