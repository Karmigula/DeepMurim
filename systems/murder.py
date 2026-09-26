"""The poisoned master (phase 4h spec 4): a natural death that was not, its clues, and what exposure costs.

When a staffed faction's leader dies of age or illness and someone had a motive, a seeded roll makes it a
poisoning: a `murder` plot. The world sees a natural death, but whispers of poison put the seat in doubt
(4g's cause `suspicion`, read from the faction's `poisoned`).
"""

import systems.claimants as C
import systems.lives as lives
import systems.plots as P
import systems.succession_crisis as SC
import systems.world_clock as world_clock
from systems import factions as F
from systems.facts import make_variant, place_name, record_fact
from systems.kin import kin_of
from systems.membership import set_membership
from systems.tournaments import alive, realm_of
from world.events import Event, Witness, commit, effect, listen
from world.gen.materialize import people_at
from world.seed import rng_for

MURDER_CHANCE = 0.25
RED_HERRING = 0.2  # the witness and the letters point at an innocent with a motive (plan ruling 3)
NATURAL = frozenset({"age", "illness"})
WAR = -0.8
EXAMINE_BASE, EXAMINE_PER_REALM = 0.6, 0.1
POISONS = {"unorthodox_clan": "the black lotus of a poison valley", "demonic_cult": "a cult's blood-venom",
           "bandit_fort": "a crude arsenic", None: "a slow poison from the south"}


def motives(world, faction: int) -> list[tuple[int, int | None]]:
    """(plotter, patron): an ambitious elder or keeper; an agent of a faction at war; a cult's spy in its halls."""
    found = [(p, None) for p in C.staff(world, faction, ("elder", "keeper")) if C.ambitious(world, p)]
    for other, value, _ in world.relations_from(faction, "stance"):
        if value <= WAR and not world.entity(other).data.get("dissolved"):
            agents = C.staff(world, other, ("elder", "keeper", "disciple"))
            if agents:
                found.append((max(agents, key=lambda p: (realm_of(world, p), -p)), other))
    found += [(spy.data["plotter"], spy.data["patron"]) for spy in P.plots_of(world, faction, ("spy",))
              if alive(world, spy.data["plotter"])]
    return found


def poison_words(world, plotter: int, patron) -> str:
    source = patron if isinstance(patron, int) and world.entity(patron).kind == "faction" else None
    kind = world.entity(source).data["type"] if source is not None else None
    return POISONS.get(kind, POISONS[None])


def murder_events(world, faction: int, victim: int, plotter: int, patron, place: int, rng) -> list[Event]:
    """A poisoning: the plot and its three clues (the body, a witness at the seat, the plotter's quarters)."""
    present = sorted(p.id for p in people_at(world, place) if p.id not in (plotter, victim)
                     and not p.data.get("is_player") and alive(world, p.id))
    innocents = [p for p, _ in motives(world, faction) if p not in (plotter, victim)]
    blamed = rng.choice(innocents) if innocents and rng.random() < RED_HERRING else None
    points = blamed if blamed is not None else plotter
    extra = {"false": True} if blamed is not None else {}
    clues = [P.clue("body", plotter, poison=poison_words(world, plotter, patron))]
    if present:
        clues.append(P.clue("witness", points, witness=rng.choice([p for p in present if p != points] or present),
                            **extra))
    clues.append(P.clue("motive", points, at="quarters", **extra))
    return P.made_events(world, "murder", f"murder:{faction}:{victim}", plotter, faction, place, target=victim,
                         patron=patron, clues=clues)


def _poisoned(world, event, rows) -> None:
    """A leader's natural death: with someone to want it, a seeded roll makes it murder (spec 4)."""
    victim = event.actors[-1]
    if event.data.get("cause") not in NATURAL or event.data.get("poisoned_by") is not None:
        return
    for fid, _, data in rows:
        faction = world.entity(fid)
        if data.get("role") != "leader" or faction.data.get("type") not in F.STAFFED or faction.data.get("dissolved"):
            continue
        rng = rng_for(world.world_seed, f"murder:{fid}:{victim}")
        if rng.random() >= MURDER_CHANCE:
            continue
        choices = [m for m in motives(world, fid) if m[0] != victim]
        if not choices:
            continue
        plotter, patron = rng.choice(choices)
        place = event.place if event.place is not None else faction.data.get("seat")
        commit(world, murder_events(world, fid, victim, plotter, patron, place, rng))


P.DIED_HOOKS.append(_poisoned)


@listen("plot_made")
def _whispers(world, event, event_id: int) -> None:
    """Whispers of poison: the seat is in doubt (4g's `suspicion`)."""
    if event.data["type"] == "murder":
        plot = world.entity_by_seed(f"plot:{event.data['key']}")
        world.update_data(event.data["faction"], poisoned=plot.id)


# --- the clues (spec 4) --------------------------------------------------------------------------------------

def murder_of(world, occurrence):
    """The crisis's open murder plot, if it has one."""
    for pid in SC.crisis_of(occurrence).get("plots", []):
        plot = P.plot_of(world, pid)
        if plot is not None and plot.data["type"] == "murder" and plot.data["state"] == "open":
            return plot
    return None


def examine_block(world, occurrence, player: int) -> str | None:
    crisis = SC.crisis_of(occurrence)
    if crisis["phase"] != "mourning":
        return "The late master has been laid in the earth."
    if player in crisis.get("examined", []):
        return "You have looked on the late master as long as the mourners will allow."
    return None


def examine_chance(world, player: int) -> float:
    return EXAMINE_BASE + EXAMINE_PER_REALM * max(0, realm_of(world, player) - 1)


def examine_events(world, occurrence, player: int) -> list[Event]:
    place = occurrence.data["place"]
    plot = murder_of(world, occurrence)
    rng = rng_for(world.world_seed, f"murder:{occurrence.id}:examine:{player}")
    found = plot is not None and rng.random() < examine_chance(world, player)
    events = [Event("body_examined", (player,), place, {"occurrence": occurrence.id, "found": found,
                                                        "poison": _poison_of(plot) if found else None})]
    return events + (P.found_events(world, plot, "body", player, place) if found else [])


def _poison_of(plot) -> str | None:
    return next((c.get("poison") for c in plot.data["clues"] if c["kind"] == "body"), None)


@effect("body_examined")
def _examined(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "examined": crisis.get("examined", []) + [event.actors[0]]})


def night_reason(world, player: int, plot) -> bool:
    """Whether the player has cause to ask about the night this murder was done: a clue, or the whispers."""
    if P.found_by(world, plot, player):
        return True
    occurrence = SC.live(world, plot.data["faction"])
    return occurrence is not None and SC.crisis_of(occurrence)["cause"] == "suspicion"


def witness_plot(world, player: int, npc: int):
    """The open murder plot this person witnessed, if the player has reason to ask them about it."""
    for pid in P.open_plots(world):
        plot = world.entity(pid)
        if plot.data["type"] != "murder":
            continue
        witnessed = any(c["kind"] == "witness" and c.get("witness") == npc and player not in c["found_by"]
                        and not c.get("lost") for c in plot.data["clues"])
        if witnessed and night_reason(world, player, plot):
            return plot
    return None


def night_events(world, player: int, npc: int, place: int) -> list[Event]:
    """Asking about the night the master died: the witness tells what they saw."""
    plot = witness_plot(world, player, npc)
    return [Event("asked_night", (player, npc), place, {"told": plot is not None})] + (
        P.found_events(world, plot, "witness", player, place) if plot is not None else [])


# --- exposure (spec 4) ----------------------------------------------------------------------------------------

def _exposed(world, plot, exposer) -> list[Event]:
    victim = plot.data["target"]
    kin = tuple(Witness(k, "hatred", 0.8, True) for k, _ in kin_of(world, victim) if k != plot.data["plotter"])
    return [Event("murder_revealed", (plot.data["plotter"],), world.entity(plot.data["faction"]).data.get("seat"),
                  {"plot": plot.id, "victim": victim, "faction": plot.data["faction"], "patron": plot.data["patron"],
                   "held_seat": C.role_in(world, plot.data["plotter"], plot.data["faction"]) == "leader"},
                  witnesses=kin)]


@effect("murder_revealed")
def _revealed(world, event) -> None:
    d = event.data
    plotter = event.actors[0]
    found = F.membership(world, plotter, d["faction"])
    if found and found[1].get("status", "member") == "member":
        set_membership(world, plotter, d["faction"], status="expelled")
    patron = d["patron"]
    if isinstance(patron, int) and world.entity(patron).kind == "faction":
        world.relate(d["faction"], patron, "stance", -1.0)
        world.relate(patron, d["faction"], "stance", -1.0)


@listen("murder_revealed")
def _revealed_news(world, event, event_id: int) -> None:
    plotter = event.actors[0]
    if event.data.get("held_seat"):  # the murderer sat in the seat: it is filled now, not next season
        commit(world, world_clock.succession_events(world, event.data["faction"], lives.current_season(world)))
    variant = make_variant("murdered", plotter, event.data["victim"], place=place_name(world, event.place))
    record_fact(world, plotter, "murdered", event.data["victim"], place=event.place, source_event=event_id,
                weight=3.0, variant=variant)


P.EXPOSE_HOOKS["murder"] = _exposed
