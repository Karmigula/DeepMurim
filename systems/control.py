"""Control pills (phase 5c spec 6): a worm in the belly, and a master who holds the only antidote.

The bound carry `bound_to = {master, since, fed_until}`. A master feeds the antidote each month; an NPC master
always does, unless dead. Past `fed_until` each day does internal harm, and after ninety the worms wake. Freedom
is the master's death, a grade-5 antidote, a famous doctor, or forcing the worms out at realm 5. The player may be
bound (spared by an unorthodox master after a real duel), may bind (a control pill forced on the beaten), and the
world's unorthodox masters bind a few of their own. The meta row `bound` lists the NPCs bound, so only they are
looked at each season. The recipe is secret: only an unorthodox sect's hall keeps it, and no experiment finds it.
"""

import systems.alchemy as A
import systems.lives as lives
import systems.npc_alchemy  # noqa: F401  its agenda runs before the world's binding
import systems.physic as PY
import systems.world_clock as world_clock
from systems import factions as F
from systems.bodies import load_body, save_body
from systems.facts import make_variant, place_name, record_fact
from systems.realms import realm_index
from world.body import WATCHES_PER_DAY, add_injury
from world.events import Event, Witness, effect, listen
from world.gen.materialize import people_at, town_label
from world.gen.region import region_spec
from world.seed import rng_for

MONTH = 30 * WATCHES_PER_DAY
STARVE_SEVERITY, STARVE_DAYS = 2, 90
FREE_GRADE = 5             # an antidote this strong kills the worms
FORCE_REALM, FORCE_QI, FORCE_CHANCE = 5, 30.0, 0.5
BIND_REALM, BIND_CHANCE = 3, 0.25   # an unorthodox master spares the player, and binds them
CURE_SEEK = 0.25           # a season's chance that one the player binds finds a cure
WORLD_BIND, WORLD_MAX = 0.02, 2     # an unorthodox master of realm 3 binds someone in a season, up to two
SERVICES = ("message", "beat", "steal")


def bound(world, person: int) -> dict | None:
    entity = world.entity(person)
    return entity.data.get("bound_to") if entity is not None else None


def servants_of(world, master: int) -> list[int]:
    return [p for p in world.get_meta("bound") or [] if (bound(world, p) or {}).get("master") == master
            and not world.entity(p).data.get("dead")]


def _index(world, person: int, on: bool) -> None:
    if world.entity(person).data.get("is_player"):
        return
    listed = [p for p in world.get_meta("bound") or [] if p != person]
    world.set_meta("bound", listed + ([person] if on else []))


def bind(world, person: int, master: int) -> None:
    world.update_data(person, bound_to={"master": master, "since": world.time, "fed_until": world.time + MONTH,
                                        "hurt_to": world.time + MONTH})
    _index(world, person, True)


def free(world, person: int) -> None:
    world.update_data(person, bound_to=None)
    _index(world, person, False)


def days_starved(world, person: int) -> float:
    b = bound(world, person)
    return max(0.0, (world.time - b["fed_until"]) / WATCHES_PER_DAY) if b else 0.0


def starve(world, person: int) -> None:
    """The days past feeding, each an internal wound, brought up to now (lazily, on the day each fell)."""
    b = bound(world, person)
    if not b or world.time <= b["fed_until"]:
        return
    start = max(b["fed_until"], b.get("hurt_to", b["fed_until"]))
    days = int((world.time - start) // WATCHES_PER_DAY)
    if days <= 0:
        return
    body = load_body(world, person)
    for day in range(1, days + 1):
        add_injury(body, "torso", "internal", STARVE_SEVERITY, start + day * WATCHES_PER_DAY, "the worms of a control pill")
    save_body(world, person, body)
    world.update_data(person, bound_to={**b, "hurt_to": start + days * WATCHES_PER_DAY})


def death_events(world, person: int) -> list[Event]:
    """Past ninety days unfed the worms wake: the death they bring, laid at the master's door."""
    b = bound(world, person)
    entity = world.entity(person)
    if not b or entity.data.get("dead") or days_starved(world, person) <= STARVE_DAYS:
        return []
    master = b["master"] if world.entity(b["master"]) is not None else person
    if entity.data.get("is_player"):
        from systems.mortality import death_events as dying
        return dying(world, person, "control_pill", master)
    return [Event("died", (master, person), lives.home(world, person), {"cause": "control_pill", "world": True})]


def fed(world, master: int) -> bool:
    """An NPC master feeds their bound always, while alive (spec 6)."""
    entity = world.entity(master)
    return entity is not None and not entity.data.get("dead") and not entity.data.get("is_player")


def season_hook(world, n: int) -> list[Event]:
    """The bound NPCs: fed by their living NPC masters, freed by a dead one, starved by a careless player; those the
    player binds may find a cure."""
    events = []
    for person in list(world.get_meta("bound") or []):
        entity = world.entity(person)
        b = bound(world, person)
        if entity is None or entity.data.get("dead") or not b:
            _index(world, person, False)
            continue
        master = world.entity(b["master"])
        if master is None or master.data.get("dead"):
            events.append(Event("control_freed", (person,), lives.home(world, person), {"how": "master_dead"}))
            continue
        if fed(world, b["master"]):
            world.update_data(person, bound_to={**b, "fed_until": world.time + MONTH, "hurt_to": world.time + MONTH})
            continue
        if rng_for(world.world_seed, f"cure_seek:{person}:{n}").random() < CURE_SEEK:
            events.append(Event("control_freed", (person,), lives.home(world, person), {"how": "doctor"}))
            continue
        starve(world, person)
        events += death_events(world, person)
    return events


world_clock.SEASON_HOOKS.append(season_hook)


@effect("control_freed")
def _freed(world, event) -> None:
    free(world, event.actors[0])


@listen("control_freed")
def _freed_news(world, event, event_id: int) -> None:
    person = event.actors[0]
    record_fact(world, person, "freed", None, place=event.place, source_event=event_id, weight=1.0,
                variant=make_variant("freed", person, None, place=place_name(world, event.place)))


@listen("succession")
def _heir_unlisted(world, event, event_id: int) -> None:
    """The heir becomes the player, whose worms are weighed turn by turn; one who steps aside bound is watched with
    the world's (5c review, as 5b's poisoned index)."""
    old, heir = event.actors
    listed = [p for p in world.get_meta("bound") or [] if p != heir]
    if not world.entity(old).data.get("dead") and bound(world, old) and old not in listed:
        listed.append(old)
    world.set_meta("bound", listed)


@listen("died")
def _master_dies(world, event, event_id: int) -> None:
    """Nothing more is owed to a dead master: their bound are free, and grateful to whoever killed them."""
    killer, dead = event.actors[0], event.actors[-1]
    if world.entity(dead).data.get("bound_to"):
        world.update_data(dead, bound_to=None)
        _index(world, dead, False)
    player = world.get_meta("player_id")
    freed = servants_of(world, dead) + ([player] if isinstance(player, int)
                                        and (bound(world, player) or {}).get("master") == dead else [])
    for person in freed:
        free(world, person)
        if killer != dead and person != killer:
            world.add_memory(person, event_id, "grateful", 0.8, False, ignore_existing=True)


# --- the worms fought ---------------------------------------------------------------------------------------

def antidote_frees(world, person: int, grade: int) -> None:
    """A grade-5 antidote swallowed kills the worms (spec 6)."""
    if grade >= FREE_GRADE and bound(world, person):
        free(world, person)


def force_block(world, person: int) -> str | None:
    if not bound(world, person):
        return "No worms sleep in you."
    body = load_body(world, person)
    if body.realm < FORCE_REALM:
        return "Only a transcendent master can force the worms out."
    if body.qi < FORCE_QI:
        return "Your qi is too low to drive them out."
    return None


def force_events(world, person: int, place) -> list[Event]:
    roll = rng_for(world.world_seed, f"force_worms:{person}:{world.time}").random()
    return [Event("worms_forced", (person,), place, {"cleared": roll < FORCE_CHANCE})]


@effect("worms_forced")
def _forced(world, event) -> None:
    person = event.actors[0]
    body = load_body(world, person)
    body.qi = max(0.0, body.qi - FORCE_QI)
    save_body(world, person, body)
    if event.data["cleared"]:
        free(world, person)


PY.CURE_HOOKS["control"] = (lambda world, person: bool(bound(world, person)), free)


# --- the player bound -----------------------------------------------------------------------------------------

def binds(world, npc: int) -> bool:
    """An unorthodox master of realm 3 or more (the realm first: it is read without a query)."""
    return realm_index(world.entity(npc).data.get("realm", "mortal")) >= BIND_REALM and PY.unorthodox(world, npc)


@listen("duel_ended")
def _spared_and_bound(world, event, event_id: int) -> None:
    """After a real duel lost to an unorthodox master who spares them, the player may wake with the worms."""
    player, opponent = event.actors
    d = event.data
    if d.get("result") != "lost" or d.get("by") != "opponent" or d.get("mode") not in ("duel", "encounter") \
            or d.get("verdict") not in ("spare", "rob") or bound(world, player) or not binds(world, opponent):
        return
    if rng_for(world.world_seed, f"bound:{event_id}").random() < BIND_CHANCE:
        bind(world, player, opponent)


def service(world, person: int) -> dict | None:
    """This month's service the master demands (seeded): carry a message, beat a fighter, or steal from a sect."""
    b = bound(world, person)
    if not b:
        return None
    month = world.time // MONTH
    rng = rng_for(world.world_seed, f"service:{person}:{b['master']}:{month}")
    kind = rng.choice(SERVICES)
    out = {"kind": kind, "month": month}
    if kind == "message":
        here = world.entity(lives.home(world, person) or 0)
        x = (here.data["x"] if here is not None and here.kind == "town" else 0) + rng.randint(-2, 2)
        y = (here.data["y"] if here is not None and here.kind == "town" else 0) + rng.randint(-2, 2)
        i = rng.randrange(region_spec(world.world_seed, x, y).town_count)
        out.update(at=[x, y, i], town=town_label(world, x, y, i))
    return out


def service_done(world, person: int) -> bool:
    """Whether this month's service is done: the town reached, a fighter beaten, or a sect robbed unseen."""
    task = service(world, person)
    if task is None or (world.entity(person).data.get("served_month") == task["month"]):
        return False
    since = task["month"] * MONTH
    if task["kind"] == "message":
        here = world.entity(lives.home(world, person) or 0)
        return here is not None and here.kind == "town" and [here.data["x"], here.data["y"], here.data["index"]] \
            == task["at"]
    for entry in world.chronicle_about(person, limit=40):
        if entry.time < since:
            break
        if task["kind"] == "beat" and entry.kind == "duel_ended" and entry.data.get("result") == "won" \
                and entry.data.get("mode") in ("duel", "encounter") and entry.actors[0] == person:
            return True
        if task["kind"] == "steal" and entry.kind == "hall_theft" and not entry.data.get("caught"):
            return True
    return False


def served_events(world, person: int, place) -> list[Event]:
    task = service(world, person)
    return [Event("service_rendered", (person, bound(world, person)["master"]), place, {"kind": task["kind"],
                                                                                      "month": task["month"]})]


@effect("service_rendered")
def _served(world, event) -> None:
    person = event.actors[0]
    b = bound(world, person)
    until = max(b["fed_until"], world.time) + MONTH
    world.update_data(person, bound_to={**b, "fed_until": until, "hurt_to": until}, served_month=event.data["month"])


# --- the player as master -------------------------------------------------------------------------------------

def control_pills(world, person: int) -> list[int]:
    import systems.pills as P
    return [p.id for p in P.pills_of(world, person) if P.effect_of(p) == "control"]


def force_feed_block(world, person: int, npc: int, place) -> str | None:
    from systems.spoils import beaten_by
    entity = world.entity(npc)
    if entity is None or entity.data.get("dead") or place not in world.targets(npc, "located_in"):
        return "They are not here."
    if entity.data.get("beast"):
        return "A beast is bound by nothing."
    if not beaten_by(world, person, npc):
        return "You have not beaten them."
    if bound(world, npc):
        return "They are bound already."
    if not control_pills(world, person):
        return "You carry no control pill."
    return None


def force_feed_events(world, person: int, npc: int, place) -> list[Event]:
    from systems.spoils import lawful
    return [Event("control_forced", (person, npc), place, {"pill": control_pills(world, person)[0],
                                                           "lawful": lawful(world, npc, place)},
                  witnesses=(Witness(npc, "hatred", 1.0, True),))]


@effect("control_forced")
def _force_fed(world, event) -> None:
    person, npc = event.actors
    world.unrelate(person, "owns", event.data["pill"])
    world.update_data(event.data["pill"], used=True)
    bind(world, npc, person)
    if not F.memberships(world, npc) and not world.entity(npc).data.get("sworn_to"):
        world.update_data(npc, sworn_to=person)  # the bound obey (3c's followers)


@listen("control_forced")
def _enslaved(world, event, event_id: int) -> None:
    if not event.data["lawful"]:
        return
    person, npc = event.actors
    record_fact(world, person, "enslaved", npc, place=event.place, source_event=event_id, weight=2.0,
                variant=make_variant("enslaved", person, npc, place=place_name(world, event.place)))


def feed_block(world, person: int, npc: int) -> str | None:
    if (bound(world, npc) or {}).get("master") != person:
        return "They are not bound to you."
    if not control_pills(world, person):
        return "You carry no control pill to send them."
    return None


def feed_events(world, person: int, npc: int, place) -> list[Event]:
    return [Event("servant_fed", (person, npc), place, {"pill": control_pills(world, person)[0]})]


@effect("servant_fed")
def _fed(world, event) -> None:
    person, npc = event.actors
    world.unrelate(person, "owns", event.data["pill"])
    world.update_data(event.data["pill"], used=True)
    b = bound(world, npc)
    until = max(b["fed_until"], world.time) + MONTH
    world.update_data(npc, bound_to={**b, "fed_until": until, "hurt_to": until})


# --- freeing another -------------------------------------------------------------------------------------------

def antidote_for(world, person: int) -> int | None:
    import systems.pills as P
    return next((p.id for p in P.pills_of(world, person) if P.effect_of(p) == "antidote"
                 and P.grade_of(p) >= FREE_GRADE), None)


def free_block(world, person: int, npc: int, place) -> str | None:
    if not bound(world, npc) or bound(world, npc)["master"] == person:
        return "No one holds them."
    if place not in world.targets(npc, "located_in"):
        return "They are not here."
    if antidote_for(world, person) is None:
        return "Only a grade-5 antidote kills the worms."
    return None


def free_events(world, person: int, npc: int, place) -> list[Event]:
    return [Event("worms_killed", (person, npc), place, {"pill": antidote_for(world, person)},
                  witnesses=(Witness(npc, "saved", 1.0),))]


@effect("worms_killed")
def _killed(world, event) -> None:
    person, npc = event.actors
    world.unrelate(person, "owns", event.data["pill"])
    world.update_data(event.data["pill"], used=True)
    free(world, npc)


@listen("worms_killed")
def _killed_news(world, event, event_id: int) -> None:
    person, npc = event.actors
    record_fact(world, person, "freed", npc, place=event.place, source_event=event_id, weight=1.5,
                variant=make_variant("freed", person, npc, place=place_name(world, event.place)))


# --- the world's masters ------------------------------------------------------------------------------------

def world_events(world, person: int, n: int, rng) -> list[Event]:
    """An unorthodox master of realm 3 binds someone of their town now and then, two at most (a lives agenda)."""
    if not binds(world, person) or len(servants_of(world, person)) >= WORLD_MAX:
        return []
    mine = rng_for(world.world_seed, f"world_bind:{lives.key(world.entity(person))}:{n}")
    if mine.random() >= WORLD_BIND:
        return []
    town = lives.home(world, person)
    victims = sorted(p.id for p in people_at(world, town) if p.id != person and lives.simulated(p)
                     and not p.data.get("bound_to")) if town is not None else []
    if not victims:
        return []
    return [Event("npc_bound", (person, mine.choice(victims)), town, {"season": n})]


lives.AGENDAS.append(world_events)


@effect("npc_bound")
def _npc_bound(world, event) -> None:
    master, victim = event.actors
    bind(world, victim, master)


@listen("npc_bound")
def _npc_bound_news(world, event, event_id: int) -> None:
    master, victim = event.actors
    record_fact(world, master, "enslaved", victim, place=event.place, source_event=event_id, weight=1.5,
                variant=make_variant("enslaved", master, victim, place=place_name(world, event.place)))
