"""Puppets and cult spies (phase 4h spec 5).

A hostile sect may back a claimant in a crisis with silver and a fighter (a `puppet` plot, its envoy at the
seat); a winning puppet puts the sect in the patron's pocket. A demonic cult may plant a spy among an
orthodox sect's keepers and disciples (a `spy` plot): in peace they steal arts, in a crisis they are a motive
for murder and a vote for the cult's puppet.
"""

import systems.claimants as C
import systems.plots as P
import systems.succession_crisis as SC
import systems.world_clock as world_clock
from systems import factions as F
from systems import founding
from systems.attitude import attitude
from systems.facts import make_variant, place_name, record_fact
from systems.membership import set_membership
from systems.tournaments import alive, realm_of
from world.events import Event, Witness, commit, effect, listen
from world.gen.materialize import people_at
from world.seed import rng_for

HOSTILE = -0.5
PUPPET_CHANCE, PUPPET_REACH = 0.3, 3
GIFT = 0.2
POCKET_STANCE = 0.3
EXPOSED_LEAN, EXPOSED_STANCE = -0.5, -0.3
SPY_CHANCE, THEFT_CHANCE = 0.02, 0.1
SPY_STANCE = -0.2


def _stance(world, a: int, b: int) -> float:
    return F.stance(world, a, b)


# --- puppets (spec 5.1) --------------------------------------------------------------------------------------

def patrons(world, faction: int) -> list[int]:
    """Factions hostile to this one, within reach of its seat, that could back a puppet."""
    data = world.entity(faction).data
    home = data.get("home")
    out = []
    for other, value, _ in world.relations_from(faction, "stance"):
        o = world.entity(other)
        if value <= HOSTILE and not o.data.get("dissolved") and o.data.get("home") is not None and home is not None \
                and F.gap(home, o.data["home"]) <= PUPPET_REACH and C.staff(world, other, ("leader", "elder")):
            out.append(other)
    return sorted(out)


def puppet_events(world, occurrence, patron: int, claimant: int, key: str, plotter: int | None = None) -> list[Event]:
    """A puppet plot: its envoy at the seat (made on the spot unless given) and its two clues."""
    crisis, seat = SC.crisis_of(occurrence), occurrence.data["place"]
    envoy = plotter
    if envoy is None:
        envoy = founding.make_person(world, f"envoy:{key}", seat, occupation="wandering swordsman", age=35,
                                     realm="second-rate")
        world.relate(envoy, patron, "member_of", 1, {"role": "member", "hall": None, "merit": 0, "status": "member",
                                                     "secret": False})
    fighters = C.staff(world, patron, ("elder",)) if world.entity(patron).kind == "faction" else []
    lent = max(fighters, key=lambda p: (realm_of(world, p), -p)) if fighters else None
    clues = [P.clue("silver", envoy), P.clue("envoy", envoy)]
    return P.made_events(world, "puppet", key, envoy, crisis["faction"], seat, target=crisis["faction"],
                         patron=patron, serves=claimant, clues=clues,
                         extra={"occurrence": occurrence.id, "lent": lent, "gifted": []})


def _backed(world, occurrence) -> None:
    """A crisis begins: a hostile sect within reach may back a claimant (0.3)."""
    faction = SC.crisis_of(occurrence)["faction"]
    rng = rng_for(world.world_seed, f"puppet:{occurrence.id}")
    options = patrons(world, faction)
    crisis = SC.crisis_of(occurrence)
    claimants = [c["person"] for c in crisis["claimants"] if not world.entity(c["person"]).data.get("is_player")]
    if not options or not claimants or rng.random() >= PUPPET_CHANCE:
        return
    patron = rng.choice(options)
    heads = C.staff(world, patron, ("leader",))
    if heads:
        claimant = max(claimants, key=lambda p: (attitude(world, heads[0], p).score, -p))
    else:
        claimant = min(claimants, key=lambda p: (realm_of(world, p), p))
    commit(world, puppet_events(world, occurrence, patron, claimant, f"puppet:{occurrence.id}"))


@listen("plot_made")
def _lends(world, event, event_id: int) -> None:
    """The patron's fighter stands as the puppet's champion; the cult's spies declare for the cult's puppet."""
    d = event.data
    if d["type"] != "puppet":
        return
    plot = world.entity_by_seed(f"plot:{d['key']}")
    occurrence = world.entity(plot.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    champions = dict(crisis.get("champions", {}))
    if plot.data.get("lent") is not None and str(d["serves"]) not in champions:
        champions[str(d["serves"])] = plot.data["lent"]
    declared = dict(crisis.get("declared", {}))
    for spy in P.plots_of(world, crisis["faction"], ("spy",)):
        if spy.data["patron"] == d["patron"] and alive(world, spy.data["plotter"]):
            declared[str(spy.data["plotter"])] = d["serves"]
    world.update_data(occurrence.id, data={**crisis, "champions": champions, "declared": declared,
                                           "plots": crisis.get("plots", []) + [plot.id]})


@listen("crisis_phase")
def _silver(world, event, event_id: int) -> None:
    """At the mourning's end the puppet's camp spends the patron's silver: a gift-sway to each voter of rank 2+."""
    if event.data["phase"] != "canvass":
        return
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    for plot in P.plots_of(world, crisis["faction"], ("puppet",)):
        if plot.data.get("occurrence") != occurrence.id:
            continue
        puppet = str(plot.data["serves"])
        sways = {k: dict(v) for k, v in crisis.get("sways", {}).items()}
        gifted = []
        for voter in C.voters(world, crisis["faction"]):
            found = F.membership(world, voter, crisis["faction"])
            if voter == plot.data["serves"] or world.entity(voter).data.get("is_player") or not found or found[0] < 2:
                continue
            mine = sways.setdefault(str(voter), {})
            mine[puppet] = round(mine.get(puppet, 0.0) + GIFT, 3)
            gifted.append(voter)
        crisis = {**crisis, "sways": sways}
        world.update_data(plot.id, gifted=gifted)
    world.update_data(occurrence.id, data=crisis)


def gift_plot(world, player: int, npc: int):
    """The open puppet plot this voter took silver from, at the player's town."""
    here = world.targets(player, "located_in")
    for plot in [world.entity(p) for p in P.open_plots(world)]:
        if plot.data["type"] == "puppet" and npc in plot.data.get("gifted", []) \
                and P.unfound(plot, "silver", player) is not None \
                and (P.knows(world, player, plot) or P.found_by(world, plot, player)) \
                and here == [world.entity(plot.data["faction"]).data.get("seat")]:
            return plot
    return None


def envoy_plot(world, player: int, npc: int):
    """The open puppet plot whose envoy this is, if the player has not yet found them out."""
    for plot in [world.entity(p) for p in P.open_plots(world)]:
        if plot.data["type"] == "puppet" and plot.data["plotter"] == npc and P.unfound(plot, "envoy", player):
            return plot
    return None


def asked_events(world, player: int, npc: int, place: int, what: str) -> list[Event]:
    """Asking a voter about the gift they took, or a stranger where they come from."""
    plot = gift_plot(world, player, npc) if what == "silver" else envoy_plot(world, player, npc)
    return [Event("asked_about", (player, npc), place, {"what": what, "told": plot is not None})] + (
        P.found_events(world, plot, what, player, place) if plot is not None else [])


@listen("crisis_settled")
def _pocket(world, event, event_id: int) -> None:
    """A puppet who wins puts the sect in the patron's pocket (spec 5.1)."""
    for plot in P.plots_of(world, event.data["faction"], ("puppet",)):
        if plot.data["serves"] == event.data["winner"] and world.entity(plot.data["patron"]).kind == "faction":
            a, b = event.data["faction"], plot.data["patron"]
            world.relate(a, b, "stance", POCKET_STANCE)
            world.relate(b, a, "stance", POCKET_STANCE)
            world.update_data(a, pocket={"patron": b, "puppet": event.data["winner"]})
        plotter = plot.data["plotter"]
        if plot.data["serves"] == event.data["winner"] and world.entity(plotter).data.get("is_player"):
            commit(world, [Event("puppet_thanks", (plotter, event.data["winner"]), event.place, {},
                                 witnesses=(Witness(event.data["winner"], "grateful", 0.8),))])  # spec 8
        commit(world, [Event("plot_closed", (), None, {"plot": plot.id, "state": "void"})])  # its crisis is over


def in_pocket(world, a: int, b: int) -> bool:
    """Whether one of these factions is in the other's pocket, its puppet still leading."""
    for x, y in ((a, b), (b, a)):
        pocket = world.entity(x).data.get("pocket")
        if pocket and pocket["patron"] == y and C.role_in(world, pocket["puppet"], x) == "leader":
            return True
    return False


def _puppet_exposed(world, plot, exposer) -> list[Event]:
    return [Event("puppet_revealed", (plot.data["serves"],), world.entity(plot.data["faction"]).data.get("seat"),
                  {"plot": plot.id, "faction": plot.data["faction"], "patron": plot.data["patron"]})]


@effect("puppet_revealed")
def _revealed(world, event) -> None:
    d = event.data
    puppet = event.actors[0]
    occurrence = SC.live(world, d["faction"])
    if occurrence is not None:
        crisis = SC.crisis_of(occurrence)
        sways = {k: dict(v) for k, v in crisis.get("sways", {}).items()}
        for voter in C.voters(world, d["faction"]):
            mine = sways.setdefault(str(voter), {})
            mine[str(puppet)] = round(mine.get(str(puppet), 0.0) + EXPOSED_LEAN, 3)  # a foreign creature
        world.update_data(occurrence.id, data={**crisis, "sways": sways})
    patron = d["patron"]
    if isinstance(patron, int) and world.entity(patron).kind == "faction":
        value = max(-1.0, _stance(world, d["faction"], patron) + EXPOSED_STANCE)
        world.relate(d["faction"], patron, "stance", value)
        world.relate(patron, d["faction"], "stance", value)
    if (world.entity(d["faction"]).data.get("pocket") or {}).get("puppet") == puppet:
        world.update_data(d["faction"], pocket=None)


P.EXPOSE_HOOKS["puppet"] = _puppet_exposed


# --- cult spies (spec 5.2) -----------------------------------------------------------------------------------

def spy_events(world, sect: int, cult: int, spy: int, key: str) -> list[Event]:
    seat = world.entity(sect).data.get("seat")
    present = sorted(p.id for p in people_at(world, seat) if p.id != spy and not p.data.get("is_player")
                     and alive(world, p.id)) if seat is not None else []
    rng = rng_for(world.world_seed, f"spy:{key}")
    clues = ([P.clue("night", spy, witness=rng.choice(present))] if present else []) + [P.clue("mark", spy, at="quarters")]
    return P.made_events(world, "spy", key, spy, sect, seat, target=sect, patron=cult, clues=clues)


@listen("plot_made")
def _spy_of(world, event, event_id: int) -> None:
    if event.data["type"] == "spy":
        world.update_data(event.data["plotter"], spy_of=event.data["patron"])


def planting_events(world, n: int) -> list[Event]:
    """Once a year each demonic cult may plant a spy in each orthodox sect it is hostile to (0.02)."""
    if n % 4 != C.NAMING_SEASON:
        return []
    factions = [f for f in world.entities("faction") if not f.data.get("dissolved")]
    cults = [f.id for f in factions if f.data.get("type") == "demonic_cult"]
    sects = [f.id for f in factions if f.data.get("type") == "orthodox_sect"]
    events = []
    for cult in cults:
        for sect in sects:
            if _stance(world, cult, sect) > HOSTILE:
                continue
            rng = rng_for(world.world_seed, f"spy:{cult}:{sect}:{n}")
            if rng.random() >= SPY_CHANCE:
                continue
            able = [p for p in C.staff(world, sect, ("keeper", "disciple")) if not world.entity(p).data.get("is_player")
                    and not world.entity(p).data.get("spy_of")]
            if able:
                events += spy_events(world, sect, cult, rng.choice(sorted(able)), f"spy:{cult}:{sect}:{n}")
    return events


def _spy_year(world, plot, n: int, rng) -> list[Event]:
    """In peacetime a spy may steal one of the sect's arts for the cult (spec 5.2)."""
    if n % 4 != C.NAMING_SEASON or rng.random() >= THEFT_CHANCE:
        return []
    arts = [a for a in world.entity(plot.data["faction"]).data.get("arts", [])
            if a not in world.entity(plot.data["patron"]).data.get("arts", [])]
    if not arts or world.entity(plot.data["patron"]).kind != "faction":
        return []
    return [Event("art_stolen", (plot.data["plotter"],), world.entity(plot.data["faction"]).data.get("seat"),
                  {"plot": plot.id, "cult": plot.data["patron"], "art": rng.choice(sorted(arts))})]


@effect("art_stolen")
def _stolen(world, event) -> None:
    cult = event.data["cult"]
    world.update_data(cult, arts=list(world.entity(cult).data.get("arts", [])) + [event.data["art"]])


def _spy_exposed(world, plot, exposer) -> list[Event]:
    return [Event("spy_revealed", (plot.data["plotter"],), world.entity(plot.data["faction"]).data.get("seat"),
                  {"plot": plot.id, "faction": plot.data["faction"], "cult": plot.data["patron"]})]


@effect("spy_revealed")
def _spy_revealed(world, event) -> None:
    spy, d = event.actors[0], event.data
    if F.membership(world, spy, d["faction"]):
        set_membership(world, spy, d["faction"], status="spy_exposed")
    world.update_data(spy, spy_of=None)
    if isinstance(d["cult"], int) and world.entity(d["cult"]).kind == "faction":
        value = max(-1.0, _stance(world, d["faction"], d["cult"]) + SPY_STANCE)
        world.relate(d["faction"], d["cult"], "stance", value)
        world.relate(d["cult"], d["faction"], "stance", value)


@listen("spy_revealed")
def _spy_news(world, event, event_id: int) -> None:
    spy = event.actors[0]
    variant = make_variant("spy_exposed", spy, event.data["faction"], place=place_name(world, event.place))
    record_fact(world, spy, "spy_exposed", event.data["faction"], place=event.place, source_event=event_id,
                weight=2.5, variant=variant)


P.EXPOSE_HOOKS["spy"] = _spy_exposed
P.BEGUN_HOOKS.append(_backed)
P.SEASON_HOOKS["spy"] = _spy_year
world_clock.SEASON_HOOKS.append(planting_events)
