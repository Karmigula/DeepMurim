"""Force of arms and schism (phase 4g spec 4.7, 4.8): camps that will not yield fight season by season,
and a war that drags on splits the sect.

Strife runs on the faction clock (a season hook). A camp that loses a clash loses a backer: dead at 4a's
kill rate, or gone home (plan ruling 7). The weaker camp may yield; after two seasons the losers walk out
and found a breakaway sect, within the caps, or are exiled.
"""

import systems.claimants as C
import systems.succession_crisis as SC
import systems.world_clock as world_clock
import systems.world_events as W
from systems import factions as F
from systems.facts import make_variant, place_name, record_fact
from systems.membership import set_membership
from systems.tournaments import alive, realm_of
from systems.wars import KILL_CHANCE
from world.events import Event, Witness, commit, effect, listen  # commit: the far hook
from world.gen.materialize import region_of
from world.seed import rng_for

STRIFE_SEASONS = 2
YIELD = (0.3, 0.6)  # the weaker camp yields after the first clash, after the second
PREFIXES = ("Southern", "Northern", "Eastern", "Western", "True", "New")
MAX_BREAKAWAYS = 2  # from any one faction
MAX_MINORS = 4  # minor factions in one region: past it the losers are exiled (plan ruling 8)
STANCE = -0.8
FAR_STRIFE, FAR_GAP, FAR_SCHISM = 0.2, 0.5, 0.5


# --- strife, a season at a time (spec 4.7) ----------------------------------------------------

def strength(world, camp: list[int]) -> int:
    return sum(realm_of(world, p) + 1 for p in camp if alive(world, p))


def strife_camps(world, crisis: dict) -> dict[int, list[int]]:
    """The two camps at war: each claimant's backers as last settled, less those gone home."""
    backing, _ = C.camps(world, crisis)
    gone = set(crisis["strife"].get("gone", []))
    from systems.plots import plots_of  # phase 4h: a patron's lent fighter stands in the puppet's camp
    lent = {p.data["serves"]: p.data.get("lent") for p in plots_of(world, crisis["faction"], ("puppet",))}
    return {side: [p for p in backing.get(side, [side]) + ([lent[side]] if lent.get(side) else [])
                   if p not in gone and alive(world, p)]
            for side in (crisis["strife"]["a"], crisis["strife"]["b"])}


def strife_events(world, n: int) -> list[Event]:
    """Each faction's crisis at war fights once a season (a faction clock hook)."""
    events = []
    for row in W.index(world):
        if row[W.TYPE] != SC.KIND:
            continue
        occurrence = world.entity(row[W.ID])
        crisis = SC.crisis_of(occurrence)
        if crisis["phase"] == "strife" and crisis["strife"].get("season") != n:
            events += season_of_strife(world, occurrence, n)
    return events


def season_of_strife(world, occurrence, n: int) -> list[Event]:
    crisis, place = SC.crisis_of(occurrence), occurrence.data["place"]
    strife = crisis["strife"]
    a, b = strife["a"], strife["b"]
    rng = rng_for(world.world_seed, f"crisis:{occurrence.id}:strife:{n}")
    if not alive(world, a) or not alive(world, b):  # a claimant fell: the other takes the seat
        return SC.settle_events(world, occurrence, a if alive(world, a) else b if alive(world, b) else None, "strife")
    camps = strife_camps(world, crisis)
    sa, sb = strength(world, camps[a]), strength(world, camps[b])
    winner, loser = (a, b) if rng.random() < (sa / (sa + sb) if sa + sb else 0.5) else (b, a)
    fallen = [p for p in camps[loser] if p != loser]
    victim = max(fallen, key=lambda p: (realm_of(world, p), -p)) if fallen else None
    seasons = strife["seasons"] + 1
    events = [Event("strife_clash", (winner, loser), place,
                    {"occurrence": occurrence.id, "season": n, "victim": victim,
                     "dies": victim is not None and rng.random() < KILL_CHANCE})]
    if events[0].data["dies"]:
        killer = max(camps[winner], key=lambda p: (realm_of(world, p), -p))
        events.append(Event("died", (killer, victim), place, {"cause": "clash", "world": True}))
    left = [p for p in camps[loser] if p != victim]
    weaker = loser if strength(world, left) <= strength(world, camps[winner]) else winner
    other = a if weaker == b else b
    if len(left) <= 1 and weaker == loser or rng.random() < YIELD[min(seasons, STRIFE_SEASONS) - 1]:
        return events + SC.settle_events(world, occurrence, other, "strife")
    if seasons >= STRIFE_SEASONS:
        split = schism_events(world, crisis["faction"], place, weaker, other, camps[weaker], str(occurrence.id),
                              occurrence.id)
        return events + split + SC.settle_events(world, occurrence, other, "strife")
    return events


@effect("strife_clash")
def _clash(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    strife = dict(crisis["strife"])
    strife.update(seasons=strife["seasons"] + 1, season=event.data["season"])
    if event.data["victim"] is not None and not event.data["dies"]:
        strife["gone"] = list(strife.get("gone", [])) + [event.data["victim"]]  # beaten, they go home
    world.update_data(occurrence.id, data={**crisis, "strife": strife})


# --- schism (spec 4.8) ------------------------------------------------------------------------

def breakaways(world, faction: int) -> list[int]:
    return [f.id for f in world.entities("faction") if f.data.get("parent") == faction]


def _name(world, faction: int, rng) -> str | None:
    used = {f.name for f in world.entities("faction")}
    old = world.entity(faction).name
    for prefix in rng.sample(PREFIXES, len(PREFIXES)):
        name = f"{prefix} {old}"
        if name not in used:
            return name
    return None


def schism_events(world, faction: int, place: int, loser: int, winner: int, camp: list[int], key: str,
                  occurrence: int | None = None) -> list[Event]:
    """The losing camp walks out: a breakaway sect, or exile past the caps."""
    followers = sorted(p for p in camp if p != loser and alive(world, p))
    rng = rng_for(world.world_seed, f"crisis:{key}:schism")
    region = region_of(world, place)
    name = _name(world, faction, rng)
    full = len(breakaways(world, faction)) >= MAX_BREAKAWAYS or len(region.data.get("minors", [])) >= MAX_MINORS
    grudge = (Witness(loser, "hatred", 0.8, True), Witness(winner, "hatred", 0.8, True))
    if full or name is None:
        return [Event("exiled", (loser, winner), place, {"occurrence": occurrence, "faction": faction,
                                                        "followers": followers}, witnesses=grudge)]
    towns = [t for t in world.entity(faction).data.get("branches", [])
             if any(C.role_in(world, p, faction) == "keeper" and world.targets(p, "located_in") == [t]
                    for p in followers)]
    return [Event("schism", (loser, winner), place, {"occurrence": occurrence, "key": key, "faction": faction,
                                                     "name": name, "followers": followers, "halls": towns,
                                                     "region": region.id}, witnesses=grudge)]


@effect("schism")
def _schism(world, event) -> None:
    loser, _ = event.actors
    d = event.data
    old = world.entity(d["faction"])
    seat = d["halls"][0] if d["halls"] else world.targets(loser, "located_in")[0]
    seat_town = world.entity(seat)
    if seat_town.kind != "town":
        seat = old.data["seat"]
        seat_town = world.entity(seat)
    power = min(60, 25 + 5 * len(d["followers"]))
    data = {"type": old.data["type"], "tier": "minor", "home": [seat_town.data["x"], seat_town.data["y"]],
            "seat": seat, "path": old.data["path"], "ranks": list(old.data["ranks"]), "power": power,
            "base_power": power, "wealth": 20, "treasury": 100, "forms": list(old.data.get("forms", [])),
            "arts": list(old.data.get("arts", [])), "branches": [t for t in d["halls"] if t != seat],
            "parent": old.id}
    new = world.add_entity("faction", d["name"], data, f"schism:{d['key']}")
    for town in d["halls"]:
        town_data = world.entity(town).data
        world.update_data(town, halls=[f for f in town_data.get("halls", []) if f != old.id] + [new])
    here = world.entity(seat).data
    world.update_data(seat, halls=list(dict.fromkeys([*here.get("halls", []), new])),
                      seats=[*here.get("seats", []), new])
    world.update_data(old.id, branches=[t for t in old.data.get("branches", []) if t not in d["halls"]])
    for person, rank, role in [(loser, 4, "leader")] + [(p, *_post(world, p, old.id)) for p in d["followers"]]:
        if F.membership(world, person, old.id):
            set_membership(world, person, old.id, status="released")
        world.relate(person, new, "member_of", rank, {"role": role, "hall": None, "merit": 0, "status": "member",
                                                     "secret": False})
        if not world.entity(person).data.get("is_player"):
            world.update_data(person, occupation=F.title(world, new, rank) if role != "keeper" else "hall keeper")
    region = world.entity(d["region"])
    minors = list(region.data.get("minors", []))
    F._set_stances(world, [new], F.ensure_roster(world) + minors)
    world.relate(new, old.id, "stance", STANCE)
    world.relate(old.id, new, "stance", STANCE)
    world.update_data(region.id, minors=[*minors, new])
    if d["occurrence"] is not None:
        crisis = SC.crisis_of(world.entity(d["occurrence"]))
        world.update_data(d["occurrence"], data={**crisis, "breakaway": new})
    else:  # far away the history line is already written: it gains its schism
        history = list(old.data.get("history", []))
        if history:
            world.update_data(old.id, history=history[:-1] + [{**history[-1], "schism": new}])


def _post(world, person: int, faction: int) -> tuple[int, str]:
    found = F.membership(world, person, faction)
    rank, role = (found[0], found[1].get("role")) if found else (1, "disciple")
    if world.entity(person).data.get("is_player"):
        return rank, "member"  # the player walks out as what they were
    return (rank, role) if role in ("elder", "keeper", "disciple") else (1, "disciple")


@effect("exiled")
def _exiled(world, event) -> None:
    loser, _ = event.actors
    for person in [loser] + list(event.data["followers"]):
        if F.membership(world, person, event.data["faction"]):
            set_membership(world, person, event.data["faction"], status="released")
        world.update_data(person, occupation="wandering swordsman")


@listen("schism")
def _schism_news(world, event, event_id: int) -> None:
    loser, winner = event.actors
    new = world.entity_by_seed(f"schism:{event.data['key']}").id
    variant = make_variant("schism", loser, event.data["faction"], place=place_name(world, event.place))
    variant.update(people=[winner], factions=[new])
    record_fact(world, loser, "schism", event.data["faction"], place=event.place, source_event=event_id, weight=3.0,
                variant=variant, extra={"breakaway": new})


@listen("exiled")
def _exiled_news(world, event, event_id: int) -> None:
    loser, winner = event.actors
    variant = make_variant("exiled", loser, event.data["faction"], place=place_name(world, event.place))
    variant.update(people=[winner])
    record_fact(world, loser, "exiled", event.data["faction"], place=event.place, source_event=event_id, weight=2.0,
                variant=variant)


@listen("crisis_settled")
def _schism_recorded(world, event, event_id: int) -> None:
    """The history line and the outcome say whether the sect split (spec 4.9)."""
    crisis = SC.crisis_of(world.entity(event.data["occurrence"]))
    new = crisis.get("breakaway")
    if new is None:
        return
    world.update_data(event.data["occurrence"], data={**crisis, "outcome": {**crisis["outcome"], "schism": new}})
    history = list(world.entity(crisis["faction"]).data.get("history", []))
    if history:
        world.update_data(crisis["faction"], history=history[:-1] + [{**history[-1], "schism": new}])


def far_strife(world, event, crisis: dict, standing: list[dict], weights: list[float], winner: int, rng) -> None:
    """Far away, a close contest may come to arms, and half of those split the sect (spec 4.6, plan ruling 9)."""
    ranked = sorted(zip(weights, [c["person"] for c in standing]), reverse=True)
    if len(ranked) < 2 or ranked[0][0] - ranked[1][0] > FAR_GAP or rng.random() >= FAR_STRIFE \
            or rng.random() >= FAR_SCHISM:
        return
    loser = next(p for _, p in ranked if p != winner)
    backing, _ = C.camps(world, crisis, full=False)
    d = event.data
    commit(world, schism_events(world, d["faction"], event.place, loser, winner, backing.get(loser, [loser]),
                                f"far:{d['faction']}:{d['season']}"))


world_clock.SEASON_HOOKS.append(strife_events)
