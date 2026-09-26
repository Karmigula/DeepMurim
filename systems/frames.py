"""The forged will, the framed heir, and the return (phase 4h spec 6).

A cunning claimant may forge the late master's will, or frame a rival with a false crime: the framed are
cast out and live on in exile, and years later come back to demand the seat. Who waits in exile is kept in
the meta row `exiles`, so the season's check never reads every person.
"""

import systems.claimants as C
import systems.lives as lives
import systems.plots as P
import systems.succession_crisis as SC
import systems.world_clock as world_clock
from systems import factions as F
from systems import founding
from systems.bodies import load_body
from systems.facts import make_variant, place_name, record_fact
from systems.membership import set_membership
from systems.tournaments import alive
from world.events import Event, commit, effect, listen
from world.gen.materialize import ensure_town
from world.gen.region import region_spec
from world.seed import rng_for

FORGE_CHANCE, FRAME_CHANCE = 0.3, 0.15
SEAL_BASE, SEAL_PER_WIT = 0.3, 0.1
EXILE_REACH = (3, 6)
RETURN_SEASONS = (12, 40)
PLAYER_RETURN = 4  # seasons before a framed player may come back to demand the seat
CRIMES = ("stole_art", "killed_disciple")
TRUTH = 0.5


def _cunning(world, person: int) -> bool:
    return "cunning" in world.entity(person).data.get("traits", ())


def exiles(world) -> list[int]:
    return list(world.get_meta("exiles", []))


# --- the forged will (spec 6.1) -------------------------------------------------------------------------------

def forgery_events(world, occurrence, forger: int, names: int, key: str) -> list[Event]:
    """A forged will read out, naming `names`; its seal and its scribe are the clues."""
    seat = occurrence.data["place"]
    scribe = founding.make_person(world, f"scribe:{key}", seat, occupation="scribe", age=50)
    clues = [P.clue("seal", forger), P.clue("scribe", forger, witness=scribe)]
    return P.made_events(world, "forgery", key, forger, SC.crisis_of(occurrence)["faction"], seat,
                         target=SC.crisis_of(occurrence)["faction"], serves=names, clues=clues,
                         extra={"occurrence": occurrence.id})


@listen("plot_made")
def _forged_will_read(world, event, event_id: int) -> None:
    d = event.data
    if d["type"] != "forgery" or d["extra"].get("occurrence") is None:
        return  # a forgery made outside a crisis's canvass reads no will out
    plot = world.entity_by_seed(f"plot:{d['key']}")
    occurrence = world.entity(plot.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "will": {"state": "read", "names": d["serves"], "holder": None,
                                                              "forged": plot.id},
                                           "plots": crisis.get("plots", []) + [plot.id]})


def examine_will_block(world, occurrence, player: int) -> str | None:
    crisis = SC.crisis_of(occurrence)
    if (crisis.get("will") or {}).get("state") != "read":
        return "No will has been read out."
    if player in crisis.get("will_examined", []):
        return "You have studied the will as closely as the elders allow."
    return None


def seal_chance(world, player: int) -> float:
    wit = load_body(world, player).physique["comprehension"] if world.entity(player).data.get("is_player") else 5
    return max(0.0, SEAL_BASE + SEAL_PER_WIT * (wit - 5))


def examine_will_events(world, occurrence, player: int) -> list[Event]:
    crisis, place = SC.crisis_of(occurrence), occurrence.data["place"]
    plot = P.plot_of(world, (crisis.get("will") or {}).get("forged"))
    rng = rng_for(world.world_seed, f"frames:{occurrence.id}:seal:{player}")
    found = plot is not None and plot.data["state"] == "open" and rng.random() < seal_chance(world, player)
    return [Event("will_examined", (player,), place, {"occurrence": occurrence.id, "found": found})] + (
        P.found_events(world, plot, "seal", player, place) if found else [])


@effect("will_examined")
def _will_examined(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "will_examined": crisis.get("will_examined", []) +
                                           [event.actors[0]]})


def _forgery_exposed(world, plot, exposer) -> list[Event]:
    return [Event("forgery_revealed", (plot.data["plotter"],), world.entity(plot.data["faction"]).data.get("seat"),
                  {"plot": plot.id, "occurrence": plot.data.get("occurrence")})]


@effect("forgery_revealed")
def _forgery_revealed(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"]) if event.data.get("occurrence") else None
    if occurrence is not None:
        crisis = SC.crisis_of(occurrence)
        if (crisis.get("will") or {}).get("forged") == event.data["plot"]:
            world.update_data(occurrence.id, data={**crisis, "will": {"state": "forged", "names": None,
                                                                      "holder": None}})


# --- framing (spec 6.2) ----------------------------------------------------------------------------------------

def frame_events(world, occurrence, framer: int, framed: int, key: str, rng) -> list[Event]:
    """A false crime pinned on a claimant: the planted evidence (in the framed's quarters) and a false witness."""
    seat = occurrence.data["place"]
    witness = founding.make_person(world, f"witness:{key}", seat, occupation="servant", age=30)
    clues = [P.clue("planted", framer, at="quarters_of", owner=framed),
             P.clue("false_witness", framer, witness=witness)]
    return P.made_events(world, "frame", key, framer, SC.crisis_of(occurrence)["faction"], seat, target=framed,
                         clues=clues, extra={"occurrence": occurrence.id, "crime": rng.choice(CRIMES)})


@listen("plot_made")
def _cast_out(world, event, event_id: int) -> None:
    """The sect believes the crime: the framed are expelled, struck from the claims, and leave (spec 6.2)."""
    d = event.data
    if d["type"] != "frame" or d["extra"].get("failed"):
        return  # a frame that did not take casts no one out (4h spec 8)
    plot = world.entity_by_seed(f"plot:{d['key']}")
    framed, faction = d["target"], d["faction"]
    commit(world, [Event("framed_out", (framed, d["plotter"]), event.place,
                         {"plot": plot.id, "faction": faction, "crime": plot.data["crime"],
                          "occurrence": plot.data["occurrence"]})])


@effect("framed_out")
def _framed_out(world, event) -> None:
    framed, d = event.actors[0], event.data
    if F.membership(world, framed, d["faction"]):
        set_membership(world, framed, d["faction"], status="expelled")
    occurrence = world.entity(d["occurrence"])
    crisis = SC.crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "claimants": [c for c in crisis["claimants"]
                                                                   if c["person"] != framed],
                                           "plots": crisis.get("plots", []) + [d["plot"]]})
    n = lives.current_season(world)
    rng = rng_for(world.world_seed, f"frames:{d['plot']}:exile")
    if world.entity(framed).data.get("is_player"):
        world.update_data(framed, framed={"plot": d["plot"], "faction": d["faction"], "since": n})
        return
    home = world.entity(world.entity(d["faction"]).data["seat"]).data
    dx, dy = rng.randint(*EXILE_REACH) * rng.choice((-1, 1)), rng.randint(*EXILE_REACH) * rng.choice((-1, 1))
    x, y = home["x"] + dx, home["y"] + dy
    town = ensure_town(world, x, y, rng.randrange(region_spec(world.world_seed, x, y).town_count))
    world.unrelate(framed, "located_in")
    world.relate(framed, town, "located_in")
    world.update_data(framed, framed={"plot": d["plot"], "faction": d["faction"], "since": n,
                                      "returns_at": n + rng.randint(*RETURN_SEASONS)})
    world.set_meta("exiles", exiles(world) + [framed])


@listen("framed_out")
def _crime_told(world, event, event_id: int) -> None:
    """The false crime is told as any deed is: believed, and false (`is_true = False`)."""
    framed, d = event.actors[0], event.data
    variant = make_variant(d["crime"], framed, d["faction"], place=place_name(world, event.place))
    record_fact(world, framed, d["crime"], d["faction"], place=event.place, source_event=event_id, weight=2.0,
                variant=variant, is_true=False, extra={"liar": event.actors[1]})  # a lie: the framer told it


def ask_plot(world, player: int, npc: int, kind: str):
    """The open plot whose `kind` clue this person holds (a scribe, a false witness), unfound by the player."""
    for plot in [world.entity(p) for p in P.open_plots(world)]:
        for c in plot.data["clues"]:
            if c["kind"] == kind and c.get("witness") == npc and player not in c["found_by"] and not c.get("lost"):
                return plot
    return None


def asked_events(world, player: int, npc: int, place: int, kind: str) -> list[Event]:
    """Asking a scribe about the will they wrote, or a witness about the crime they swore to."""
    plot = ask_plot(world, player, npc, kind)
    return [Event("asked_about", (player, npc), place, {"what": kind, "told": plot is not None})] + (
        P.found_events(world, plot, kind, player, place) if plot is not None else [])


def _frame_exposed(world, plot, exposer) -> list[Event]:
    if plot.data.get("failed"):
        return []  # the evidence never took: no one was cast out to clear
    return [Event("frame_revealed", (plot.data["target"],), world.entity(plot.data["faction"]).data.get("seat"),
                  {"plot": plot.id, "faction": plot.data["faction"], "framer": plot.data["plotter"]})]


@effect("frame_revealed")
def _frame_revealed(world, event) -> None:
    """The truth clears the framed: a player cast out is taken back; an exile will come home with it (spec 6.3)."""
    framed, d = event.actors[0], event.data
    if world.entity(framed).data.get("is_player") and F.membership(world, framed, d["faction"]):
        set_membership(world, framed, d["faction"], status="member")
        world.update_data(framed, framed=None)


@listen("frame_revealed")
def _cleared(world, event, event_id: int) -> None:
    framed = event.actors[0]
    variant = make_variant("cleared", framed, event.data["faction"], place=place_name(world, event.place))
    record_fact(world, framed, "cleared", event.data["faction"], place=event.place, source_event=event_id,
                weight=2.0, variant=variant)


# --- the crisis's canvass: forgers and framers act (spec 6.1, 6.2) ------------------------------------------

@listen("crisis_phase")
def _schemes(world, event, event_id: int) -> None:
    if event.data["phase"] != "canvass":
        return
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    rng = rng_for(world.world_seed, f"frames:{occurrence.id}:canvass")
    cunning = [c["person"] for c in SC.standing_claimants(world, crisis) if _cunning(world, c["person"])
               and not world.entity(c["person"]).data.get("is_player")]
    will = crisis.get("will") or {}
    if cunning and will.get("state") != "read" and rng.random() < FORGE_CHANCE:
        forger = cunning[0]
        commit(world, forgery_events(world, occurrence, forger, forger, f"forgery:{occurrence.id}"))
        occurrence = world.entity(occurrence.id)
        crisis = SC.crisis_of(occurrence)
    if cunning and rng.random() < FRAME_CHANCE:
        framer = cunning[-1]
        rivals = [c["person"] for c in SC.standing_claimants(world, crisis) if c["person"] != framer]
        if rivals:
            commit(world, frame_events(world, occurrence, framer, rng.choice(rivals), f"frame:{occurrence.id}", rng))


# --- the return (spec 6.3) ---------------------------------------------------------------------------------

def return_events(world, person: int, n: int) -> list[Event]:
    """The framed come back to demand the seat: a new crisis, the returned heir against whoever holds it."""
    framed = world.entity(person).data.get("framed") or {}
    faction = framed.get("faction")
    if faction is None or world.entity(faction).data.get("dissolved"):
        return []
    seat = world.entity(faction).data["seat"]
    events = [Event("heir_returned", (person,), seat, {"faction": faction, "plot": framed["plot"]})]
    claim = {"person": person, "kind": "returned", "plot": framed["plot"]}
    occurrence = SC.live(world, faction)
    if occurrence is not None:
        return events + [Event("claim_joined", (person,), seat, {"occurrence": occurrence.id, "claim": claim})]
    holders = [{"person": h, "kind": "elder"} for h in C.staff(world, faction, ("leader",))]
    if not holders:
        return events
    return events + SC.begin_events(world, faction, n, "return", [claim] + holders, None,
                                    force=world.entity(person).data.get("is_player", False))


@effect("heir_returned")
def _returned(world, event) -> None:
    person, d = event.actors[0], event.data
    seat = world.entity(d["faction"]).data["seat"]
    world.unrelate(person, "located_in")
    world.relate(person, seat, "located_in")
    world.update_data(person, framed=None)
    world.set_meta("exiles", [p for p in exiles(world) if p != person])
    plot = P.plot_of(world, d["plot"])
    if plot is not None and plot.data["state"] == "open":  # they bring the planted evidence, and the truth
        clues = [dict(c, found_by=c["found_by"] + [person]) if c["kind"] == "planted" and person not in c["found_by"]
                 else c for c in plot.data["clues"]]
        world.update_data(plot.id, clues=clues)
        P.learn(world, person, world.entity(plot.id), 1.0, "witness")


@effect("claim_joined")
def _joined(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "claimants": crisis["claimants"] + [event.data["claim"]]})


def returns_due(world, n: int) -> list[Event]:
    """Each season: exiles whose time has come, alive and free, come home (spec 6.3)."""
    events = []
    for person in exiles(world):
        entity = world.entity(person)
        framed = entity.data.get("framed") or {}
        if not alive(world, person) or entity.data.get("sealed_in"):
            if entity.data.get("dead"):
                events.append(Event("exile_ended", (), None, {"person": person}))
            continue
        if framed.get("returns_at") is not None and n >= framed["returns_at"]:
            events += return_events(world, person, n)
    return events


@effect("exile_ended")
def _exile_ended(world, event) -> None:
    world.set_meta("exiles", [p for p in exiles(world) if p != event.data["person"]])


def player_return_block(world, player: int, town: int) -> str | None:
    framed = world.entity(player).data.get("framed") or {}
    if not framed:
        return "You were never cast out."
    if world.entity(framed["faction"]).data.get("seat") != town:
        return "The seat you were cast out of is elsewhere."
    if lives.current_season(world) - framed["since"] < PLAYER_RETURN:
        return "It is too soon: the elders' anger is fresh."
    return None


P.EXPOSE_HOOKS["forgery"] = _forgery_exposed
P.EXPOSE_HOOKS["frame"] = _frame_exposed
world_clock.SEASON_HOOKS.append(returns_due)
