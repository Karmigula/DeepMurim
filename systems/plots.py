"""Hidden truths (phase 4h spec 2.2-2.3, 3): a lasting plot per murder, puppet, spy, frame or forgery.

A plot is an entity (`kind = "plot"`) with its clues and a secret fact of its truth (recorded with
`spread = False`, as 4e's fixes). The meta row `open_plots` lists the plots still open; the seasonal hooks
(leaks, burial, the trail going cold, each type's own) read only that list.

Clues are found by actions the other modules name; a finder learns the name a clue points to. Two found
clues pointing at one person let the finder accuse them; a true accusation exposes the plot.
"""

# The registries come first: the modules that fill them (murder, puppets, frames) may be imported while this one
# is still loading (the faction clock's import chain), and must find them.
EXPOSE_HOOKS: dict = {}  # type -> (world, plot entity, exposer) -> list[Event]: each type's own consequence
SEASON_HOOKS: dict = {}  # type -> (world, plot entity, n, rng) -> list[Event]: each type's own season (a spy's year)
BEGUN_HOOKS: list = []  # (world, occurrence) -> None: called once a crisis has begun (a puppet backed)

import systems.claimants as C  # noqa: E402
import systems.lives as lives  # noqa: E402
import systems.succession_crisis as SC  # noqa: E402
import systems.world_clock as world_clock  # noqa: E402
from systems import factions as F  # noqa: E402
from systems.beliefs import believe  # noqa: E402
from systems.facts import make_variant, place_name, record_fact  # noqa: E402
from systems.membership import set_membership  # noqa: E402
from systems.tournaments import alive  # noqa: E402
from world.events import Event, Witness, commit, effect, listen  # noqa: E402
from world.gen.materialize import people_at  # noqa: E402
from world.seed import rng_for  # noqa: E402

TYPES = ("murder", "puppet", "spy", "frame", "forgery")
PREDICATES = {"murder": "poisoned", "puppet": "puppet_of", "spy": "spy_for", "frame": "framed", "forgery": "forged_will"}
LEAK_CHANCE, BURY_CHANCE, COLD_SEASONS = 0.1, 0.15, 40
COLD_TYPES = frozenset({"murder", "forgery"})
NPC_EXPOSE, NPC_EXPOSE_MANY = 0.5, 0.8
FALSE_MERIT = 30
ACCUSE_CLUES = 2


# --- the model and its index --------------------------------------------------------------------------

def open_plots(world) -> list[int]:
    return list(world.get_meta("open_plots", []))


def plot_of(world, plot_id: int):
    entity = world.entity(plot_id) if plot_id is not None else None
    return entity if entity is not None and entity.kind == "plot" else None


def plots_of(world, faction: int, types=TYPES) -> list:
    """The open plots bearing on a faction."""
    out = []
    for pid in open_plots(world):
        plot = world.entity(pid)
        if plot.data["faction"] == faction and plot.data["type"] in types:
            out.append(plot)
    return out


def exposed_plotters(world, faction: int) -> set[int]:
    """Plotters whose plots against this faction were exposed: far away, they cannot win its seat (spec 10)."""
    return {p.data["plotter"] for p in world.entities("plot") if p.data["faction"] == faction
            and p.data["state"] == "exposed"}


def puppet_served(world, faction: int) -> set[int]:
    return {p.data["serves"] for p in plots_of(world, faction, ("puppet",))}


def clue(kind: str, points_to: int, **more) -> dict:
    return {"kind": kind, "points_to": points_to, "found_by": [], **more}


def made_events(world, kind: str, key: str, plotter: int, faction: int, place: int, target=None, patron=None,
                serves=None, clues=(), extra: dict | None = None) -> list[Event]:
    """A plot begins. `key` makes its seed path (one plot a key); `clues` are `clue(...)` dicts."""
    return [Event("plot_made", (plotter,), place, {
        "type": kind, "key": key, "plotter": plotter, "faction": faction, "target": target, "patron": patron,
        "serves": serves, "clues": list(clues), "extra": extra or {}})]


@effect("plot_made")
def _made(world, event) -> None:
    d = event.data
    names = {"murder": "the poisoning of {t}", "puppet": "the puppet {s}", "spy": "the spy {p}",
             "frame": "the framing of {t}", "forgery": "the forged will of {p}"}

    def name(i):
        entity = world.entity(i) if isinstance(i, int) else None
        return entity.name if entity is not None else "someone"
    title = names[d["type"]].format(t=name(d["target"]), s=name(d["serves"]), p=name(d["plotter"]))
    known = [p for p in (d["plotter"], d["patron"]) if isinstance(p, int) and world.entity(p).kind == "person"]
    data = {"type": d["type"], "plotter": d["plotter"], "patron": d["patron"], "target": d["target"],
            "faction": d["faction"], "serves": d["serves"], "made_at": world.time,
            "season": lives.current_season(world), "clues": d["clues"], "known_by": known, "state": "open",
            "fact": None, **d["extra"]}
    plot = world.add_entity("plot", title, data, f"plot:{d['key']}")
    world.set_meta("open_plots", open_plots(world) + [plot])


@listen("plot_made")
def _secret(world, event, event_id: int) -> None:
    """The truth is a fact from the start, but nobody holds it but the plotter (4e's way with a fix)."""
    d = event.data
    plot = world.entity_by_seed(f"plot:{d['key']}")
    target = d["target"] if d["type"] != "puppet" else d["patron"]
    actor = d["plotter"] if d["type"] != "puppet" else d["serves"]
    predicate = PREDICATES[d["type"]]
    variant = make_variant(predicate, actor, target if isinstance(target, int) else None,
                           place=place_name(world, event.place))
    variant["faction_of"] = d["faction"]
    fact = record_fact(world, actor, predicate, target if isinstance(target, int) else None, place=event.place,
                       source_event=event_id, weight=2.5, variant=variant, spread=False, extra={"plot": plot.id})
    world.update_data(plot.id, fact=fact)
    for knower in plot.data["known_by"]:
        believe(world, knower, fact, variant, None, 1.0, 0, "witness")


def knows(world, person: int, plot) -> bool:
    return person in plot.data["known_by"]


def learn(world, person: int, plot, confidence: float = 1.0, channel: str = "told") -> None:
    """Someone comes to know the truth of a plot."""
    if person in plot.data["known_by"]:
        return
    world.update_data(plot.id, known_by=plot.data["known_by"] + [person])
    fact = world.fact(plot.data["fact"]) if plot.data.get("fact") else None
    if fact is not None:
        believe(world, person, fact.id, fact.data["variant"], None, confidence, 0 if channel == "witness" else 1,
                channel)  # who saw it for themself heard it at no retellings


def spy_gone(world, person: int, faction: int) -> None:
    """A spy cast out of the sect they spy on, by whatever road: their plot there is over (spec 12)."""
    for plot in plots_of(world, faction, ("spy",)):
        if plot.data["plotter"] == person:
            _close(world, plot.id, "void")
    world.update_data(person, spy_of=None)


def _close(world, plot_id: int, state: str) -> None:
    world.update_data(plot_id, state=state)
    world.set_meta("open_plots", [p for p in open_plots(world) if p != plot_id])


# --- clues, suspicion, accusation (spec 3) ---------------------------------------------------------------

def unfound(plot, kind: str, finder: int) -> dict | None:
    return next((c for c in plot.data["clues"] if c["kind"] == kind and finder not in c["found_by"]
                 and not c.get("lost")), None)


def found_events(world, plot, kind: str, finder: int, place: int) -> list[Event]:
    """The finder turns up a clue of this kind (the caller has rolled for it)."""
    found = unfound(plot, kind, finder)
    if found is None:
        return []
    return [Event("clue_found", (finder, found["points_to"]), place,
                  {"plot": plot.id, "kind": kind, "points_to": found["points_to"]})]


@effect("clue_found")
def _found(world, event) -> None:
    d = event.data
    plot = world.entity(d["plot"])
    clues = [dict(c, found_by=c["found_by"] + [event.actors[0]]) if c["kind"] == d["kind"]
             and event.actors[0] not in c["found_by"] else c for c in plot.data["clues"]]
    world.update_data(plot.id, clues=clues)


@listen("clue_found")
def _clue_known(world, event, event_id: int) -> None:
    """The finder now knows a name: a private fact of their own (nobody else holds it)."""
    d = event.data
    plot = world.entity(d["plot"])
    variant = make_variant("clue", d["points_to"], plot.data["faction"], place=place_name(world, event.place))
    variant.update(kind=d["kind"], plot_type=plot.data["type"])
    fact = record_fact(world, d["points_to"], "clue", plot.data["faction"], place=event.place, source_event=event_id,
                       weight=0.5, variant=variant, spread=False, extra={"plot": plot.id})
    believe(world, event.actors[0], fact, variant, None, 0.5, 0, "witness")


QUARTERS = frozenset({"motive", "mark", "planted"})  # clues kept in someone's quarters
SEARCH_CHANCE = 0.5


def search_block(world, person: int, suspect: int) -> str | None:
    if suspect not in suspicions(world, person) and not world.entity(suspect).data.get("framed"):
        return "You have no reason to turn their quarters over."
    framed = world.entity(suspect).data.get("framed") or {}
    if framed:  # their quarters are at the seat they were cast out of, whether or not they are
        seat = world.entity(framed["faction"]).data.get("seat")
        if seat not in world.targets(person, "located_in"):
            return "Their quarters are not here."
    elif world.targets(suspect, "located_in") != world.targets(person, "located_in"):
        return "Their quarters are not here."
    if (world.entity(person).data.get("searched") or {}).get(str(suspect)) == lives.current_season(world):
        return "You searched their quarters this season."
    return None


def search_events(world, person: int, suspect: int, place: int) -> list[Event]:
    """Turning a suspect's quarters over: a chance at every quarters clue pointing at them (spec 4, 5.2, 6.2)."""
    season = lives.current_season(world)
    rng = rng_for(world.world_seed, f"plots:search:{person}:{suspect}:{season}")
    found = rng.random() < SEARCH_CHANCE
    events = [Event("quarters_searched", (person, suspect), place, {"season": season, "found": found})]
    if found:
        for pid in open_plots(world):
            plot = world.entity(pid)
            for c in plot.data["clues"]:
                here = (c.get("at") == "quarters" and c["points_to"] == suspect) or \
                    (c.get("at") == "quarters_of" and c.get("owner") == suspect)  # evidence planted on another
                if c["kind"] in QUARTERS and here and person not in c["found_by"] and not c.get("lost"):
                    events += found_events(world, plot, c["kind"], person, place)
    return events


@effect("quarters_searched")
def _searched(world, event) -> None:
    person, suspect = event.actors
    searched = dict(world.entity(person).data.get("searched") or {})
    searched[str(suspect)] = event.data["season"]
    world.update_data(person, searched=searched)


def found_by(world, plot, person: int) -> list[dict]:
    return [c for c in plot.data["clues"] if person in c["found_by"]]


def suspicions(world, person: int, faction: int | None = None) -> dict[int, list[str]]:
    """{suspect: [clue kinds]} from the open plots whose clues this person has found."""
    out: dict[int, list[str]] = {}
    for pid in open_plots(world):
        plot = world.entity(pid)
        if faction is not None and plot.data["faction"] != faction:
            continue
        for c in found_by(world, plot, person):
            out.setdefault(c["points_to"], []).append(c["kind"])
    return out


def proven(world, person: int, suspect: int, faction: int):
    """The open plot of this faction whose plotter is `suspect`, if this person found two clues pointing at them."""
    for plot in plots_of(world, faction):
        if plot.data["plotter"] == suspect and sum(1 for c in found_by(world, plot, person)
                                                   if c["points_to"] == suspect) >= ACCUSE_CLUES:
            return plot
    return None


def accuse_block(world, person: int, suspect: int, faction: int) -> str | None:
    most = max((sum(1 for c in found_by(world, plot, person) if c["points_to"] == suspect)
                for plot in plots_of(world, faction)), default=0)
    if most < ACCUSE_CLUES:  # two things of one plot: clues of two plots are no case
        return "You need two things that point at them before the elders will hear you."
    return None


def accuse_events(world, person: int, suspect: int, faction: int, place: int) -> list[Event]:
    """Before the elders: a true accusation exposes the plot; a false one costs the accuser (spec 3)."""
    plot = proven(world, person, suspect, faction)
    if plot is not None:
        return exposed_events(world, plot, person, place)
    return [Event("false_accusation", (person, suspect), place, {"faction": faction},
                  witnesses=(Witness(suspect, "wronged", 0.8, True),))]


@effect("false_accusation")
def _false(world, event) -> None:
    person, faction = event.actors[0], event.data["faction"]
    found = F.membership(world, person, faction)
    if found and found[1].get("status", "member") == "member":
        set_membership(world, person, faction, merit=max(0, found[1].get("merit", 0) - FALSE_MERIT))


@listen("false_accusation")
def _false_news(world, event, event_id: int) -> None:
    person, suspect = event.actors
    variant = make_variant("false_accusation", person, suspect, place=place_name(world, event.place))
    record_fact(world, person, "false_accusation", suspect, place=event.place, source_event=event_id, weight=1.5,
                variant=variant)


# --- exposure (spec 3) -----------------------------------------------------------------------------------

def exposed_events(world, plot, exposer: int | None, place: int) -> list[Event]:
    elders = [e for e in C.staff(world, plot.data["faction"], ("leader", "elder")) if e != plot.data["plotter"]]
    thanks = tuple(Witness(e, "grateful", 0.5) for e in elders) if exposer is not None else ()
    actors = (exposer, plot.data["plotter"]) if exposer is not None else (plot.data["plotter"],)
    events = [Event("plot_exposed", actors, place, {"plot": plot.id, "exposer": exposer})]
    if thanks:
        events.append(Event("thanked", (exposer,), place, {"plot": plot.id}, witnesses=thanks))
    hook = EXPOSE_HOOKS.get(plot.data["type"])
    return events + (hook(world, plot, exposer) if hook is not None else [])


@effect("plot_exposed")
def _exposed(world, event) -> None:
    plot = world.entity(event.data["plot"])
    _close(world, plot.id, "exposed")
    occurrence = SC.live(world, plot.data["faction"])
    if occurrence is not None:  # the plotter is struck from any claim they hold
        crisis = SC.crisis_of(occurrence)
        who = plot.data["plotter"]
        claimants = [c for c in crisis["claimants"] if c["person"] != who]
        declared = {k: v for k, v in crisis.get("declared", {}).items() if v != who}
        world.update_data(occurrence.id, data={**crisis, "claimants": claimants, "declared": declared})


@listen("plot_exposed")
def _published(world, event, event_id: int) -> None:
    """Out in the open: the truth is told like any deed (4e's publishing), now at full weight."""
    plot = world.entity(event.data["plot"])
    secret = world.fact(plot.data["fact"]) if plot.data.get("fact") else None
    if secret is None:
        return
    record_fact(world, secret.subject, secret.predicate, secret.object, place=event.place, source_event=event_id,
                weight=2.5, variant=dict(secret.data["variant"]), extra={"plot": plot.id, "exposed": True})
    if event.data["exposer"] is not None:
        learn(world, event.data["exposer"], world.entity(plot.id), 1.0, "witness")


def crisis_begun(world, occurrence) -> None:
    """A crisis has begun (4g's `_begun` calls this last): each registered hook may draw a plot into it."""
    for hook in BEGUN_HOOKS:
        hook(world, world.entity(occurrence.id))


# --- NPCs who know speak at the contest (spec 3) ----------------------------------------------------------

def contest_exposures(world, occurrence) -> None:
    """Before the contest: an NPC claimant or voter who knows a plot's truth may lay it before the elders."""
    crisis = SC.crisis_of(occurrence)
    faction, place = crisis["faction"], occurrence.data["place"]
    speakers = {c["person"] for c in crisis["claimants"]} | set(C.voters(world, faction))
    rng = rng_for(world.world_seed, f"plots:{occurrence.id}:contest")
    for plot in plots_of(world, faction):
        knowing = [p for p in plot.data["known_by"] if p in speakers and p not in (plot.data["plotter"],
                                                                                   plot.data["patron"])
                   and alive(world, p) and not world.entity(p).data.get("is_player")]
        chance = NPC_EXPOSE_MANY if len(knowing) > 1 else NPC_EXPOSE
        if knowing and rng.random() < chance:
            commit(world, exposed_events(world, plot, knowing[0], place))



# --- the seasons (spec 2.3) ------------------------------------------------------------------------------

def season_events(world, n: int) -> list[Event]:
    """Over open plots only: leaks, burial, the trail going cold, each type's own season."""
    events = []
    for pid in open_plots(world):
        plot = world.entity(pid)
        d = plot.data
        rng = rng_for(world.world_seed, f"plots:{pid}:{n}")
        if not alive(world, d["plotter"]) and d["type"] in ("spy", "puppet", "frame"):
            events.append(Event("plot_closed", (), None, {"plot": pid, "state": "void"}))
            continue
        if d["type"] in COLD_TYPES and n - d["season"] >= COLD_SEASONS:
            events.append(Event("plot_closed", (), None, {"plot": pid, "state": "cold"}))
            continue
        seat = world.entity(d["faction"]).data.get("seat")
        if seat is not None and rng.random() < LEAK_CHANCE:
            hearers = [p.id for p in people_at(world, seat) if p.id not in d["known_by"]
                       and not p.data.get("is_player")]
            if hearers:
                events.append(Event("plot_leaked", (rng.choice(sorted(hearers)),), seat, {"plot": pid}))
        witness = next((c for c in d["clues"] if c.get("witness") is not None and not c["found_by"]
                        and not c.get("lost") and alive(world, c["witness"])), None)
        if witness is not None and alive(world, d["plotter"]) and rng.random() < BURY_CHANCE:
            events.append(Event("witness_lost", (witness["witness"],), seat, {"plot": pid, "kind": witness["kind"]}))
        hook = SEASON_HOOKS.get(d["type"])
        if hook is not None:
            events += hook(world, plot, n, rng)
    return events


@effect("plot_closed")
def _closed(world, event) -> None:
    _close(world, event.data["plot"], event.data["state"])


@effect("plot_leaked")
def _leaked(world, event) -> None:
    learn(world, event.actors[0], world.entity(event.data["plot"]), 0.7, "gossip")


@effect("witness_lost")
def _witness_lost(world, event) -> None:
    """A witness goes missing: their clue is lost, and the loss points at the plotter (spec 2.3)."""
    witness, d = event.actors[0], event.data
    plot = world.entity(d["plot"])
    world.update_data(witness, vanished={"plot": plot.id, "time": world.time})
    world.unrelate(witness, "located_in")
    for faction, _, data in F.memberships(world, witness):
        if data.get("status", "member") == "member":
            set_membership(world, witness, faction, status="missing")
    clues = [dict(c, lost=True) if c["kind"] == d["kind"] else c for c in plot.data["clues"]]
    world.update_data(plot.id, clues=clues + [clue("missing", plot.data["plotter"])])


@listen("witness_lost")
def _witness_news(world, event, event_id: int) -> None:
    variant = make_variant("vanished", event.actors[0], None, place=place_name(world, event.place))
    record_fact(world, event.actors[0], "vanished", None, place=event.place, source_event=event_id, weight=1.5,
                variant=variant)


world_clock.SEASON_HOOKS.append(season_events)
