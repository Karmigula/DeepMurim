"""New ways to the seat (phase 4h spec 7): the supreme art, the founder's test, marriage into the master's
line, an arbiter's verdict, and an outsider named heir.
"""

import systems.claimants as C
import systems.lives as lives
import systems.plots as P
import systems.succession_crisis as SC
import systems.world_clock as world_clock
from systems import factions as F
from systems.agendas import _pair, spouse_of
from systems.bodies import load_body, save_body
from systems.facts import make_variant, place_name, record_fact
from systems.items import create_manual
from systems.kin import kin_of
from systems.realms import REALMS
from systems.techniques import GRADE_MULT, create_technique, generate, known_arts, teach
from systems.tournaments import alive, realm_of
from world.body import add_injury
from world.events import Event, commit, effect, listen
from world.gen.materialize import people_at
from world.seed import rng_for

ART_KNOWN = 0.5  # the completeness that shows the art
HEIR_LEARNS = 4  # seasons as chief disciple before the leader teaches them half the art
MANUAL_CHANCE, MANUAL_COMPLETENESS, MANUAL_FIND = 0.5, 0.8, 0.5
TEST_BASE, TEST_PER_REALM, TEST_PER_WIT, TEST_BOUNDS = 0.02, 0.08, 0.02, (0.02, 0.5)
TEST_DEATH, NPC_TRY = 0.3, 0.3
MARRY_CHANCE = 0.2
ARBITER_CHANCE, DEFY_CHANCE = 0.3, 0.5
OUTSIDER_CHANCE, OUTSIDER_LEAN = 0.1, -0.2
WANDERERS = frozenset({"wandering swordsman"})
RIGHTEOUS = frozenset({"alliance", "orthodox_sect"})


def great(world, faction: int) -> bool:
    data = world.entity(faction).data
    return data.get("tier") == "great" and data.get("type") in F.STAFFED


# --- the supreme art -------------------------------------------------------------------------------------

def supreme_art(world, faction: int) -> int:
    """The sect's top-grade art, made once and seeded (spec 7)."""
    found = world.entity(faction).data.get("supreme_art")
    if found is not None:
        return found
    rng = rng_for(world.world_seed, f"world:{faction}:supreme_art")
    name, data = generate(rng, "martial", grade=len(GRADE_MULT))
    art = create_technique(world, name, {**data, "origin": "supreme", "faction": faction})
    world.update_data(faction, supreme_art=art)
    return art


def art_known(world, person: int, faction: int) -> float:
    art = world.entity(faction).data.get("supreme_art")
    if art is None:
        return 0.0
    return max((a.known_completeness for a in known_arts(world, person) if a.technique.id == art), default=0.0)


def teaching_events(world, n: int) -> list[Event]:
    """Once a year a great sect's chief disciple of a year's standing is taught half the supreme art (spec 7)."""
    if n % 4 != C.NAMING_SEASON:
        return []
    events = []
    for faction in world.entities_after("faction", "heir", 0):
        heir, since = faction.data.get("heir"), faction.data.get("heir_since")
        if great(world, faction.id) and since is not None and n - since >= HEIR_LEARNS and alive(world, heir) \
                and art_known(world, heir, faction.id) < ART_KNOWN:
            events.append(Event("art_taught", (heir,), faction.data.get("seat"), {"faction": faction.id}))
    return events


@effect("art_taught")
def _taught(world, event) -> None:
    art = supreme_art(world, event.data["faction"])
    teach(world, event.actors[0], art, completeness=ART_KNOWN, known_completeness=ART_KNOWN, source="sect")


@listen("named_chief")
def _named_since(world, event, event_id: int) -> None:
    """Remember when the chief disciple was named (the art is taught after a year)."""
    world.update_data(event.data["faction"], heir_since=lives.current_season(world))


@listen("died")
def _manual_left(world, event, event_id: int) -> None:
    """A great sect's master dies: a manual of the supreme art may lie in their chambers (0.5)."""
    victim = event.actors[-1]
    for fid, _, data in F.memberships(world, victim):
        if data.get("role") != "leader" or not great(world, fid) or world.entity(fid).data.get("dissolved"):
            continue
        if world.entity(fid).data.get("art_manual") is None \
                and rng_for(world.world_seed, f"manual:{fid}:{victim}").random() < MANUAL_CHANCE:
            manual = create_manual(world, fid, supreme_art(world, fid), MANUAL_COMPLETENESS)  # the sect holds it
            world.update_data(fid, art_manual=manual)


@listen("chambers_searched")
def _manual_found(world, event, event_id: int) -> None:
    """The late master's rooms: a search that turned up no will may turn up the manual (spec 7)."""
    occurrence = world.entity(event.data["occurrence"])
    faction = SC.crisis_of(occurrence)["faction"]
    manual = world.entity(faction).data.get("art_manual")
    if manual is None or event.data["found"]:
        return
    if rng_for(world.world_seed, f"manual:{occurrence.id}:{event.actors[0]}:{event.data['season']}").random() < MANUAL_FIND:
        commit(world, [Event("manual_found", (event.actors[0],), event.place, {"faction": faction, "manual": manual})])


@effect("manual_found")
def _found(world, event) -> None:
    manual = event.data["manual"]
    for owner in world.sources(manual, "owns"):
        world.unrelate(owner, "owns", manual)
    world.relate(event.actors[0], manual, "owns")
    world.update_data(event.data["faction"], art_manual=None)


# --- the founder's test ------------------------------------------------------------------------------------

def test_chance(world, person: int) -> float:
    wit = load_body(world, person).physique["comprehension"] if world.entity(person).data.get("is_player") else 5
    low, high = TEST_BOUNDS
    return max(low, min(high, TEST_BASE + TEST_PER_REALM * (realm_of(world, person) - 2) + TEST_PER_WIT * (wit - 5)))


def test_block(world, occurrence, person: int) -> str | None:
    crisis = SC.crisis_of(occurrence)
    if not great(world, crisis["faction"]):
        return "This sect's founder left no test."
    if crisis["phase"] not in ("mourning", "canvass"):
        return "The founder's hall is closed now."
    if SC.claimant(crisis, person) is None:
        return "Only a claimant may enter the founder's hall."
    if person in crisis.get("tested", []):
        return "You have faced the founder's test."
    return None


def test_events(world, occurrence, person: int) -> list[Event]:
    """The founder's test: passing takes the seat; failing strikes the claim, and may kill (spec 7)."""
    place = occurrence.data["place"]
    rng = rng_for(world.world_seed, f"founder:{occurrence.id}:{person}")
    if rng.random() < test_chance(world, person):
        return [Event("founder_passed", (person,), place, {"occurrence": occurrence.id})] + \
            SC.settle_events(world, occurrence, person, "founder")
    dies = rng.random() < TEST_DEATH
    events = [Event("founder_failed", (person,), place, {"occurrence": occurrence.id, "dies": dies})]
    if dies and world.entity(person).data.get("is_player"):
        from systems.mortality import death_events  # the player's death goes the 4b way: dying, then an heir
        events += death_events(world, person, "founder_test", None)
    elif dies:
        events.append(Event("died", (person, person), place, {"cause": "founder_test", "world": True}))
    return events


@effect("founder_passed")
def _passed(world, event) -> None:
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "tested": crisis.get("tested", []) + [event.actors[0]]})


@effect("founder_failed")
def _failed(world, event) -> None:
    person = event.actors[0]
    occurrence = world.entity(event.data["occurrence"])
    crisis = SC.crisis_of(occurrence)
    world.update_data(occurrence.id, data={**crisis, "tested": crisis.get("tested", []) + [person],
                                           "claimants": [c for c in crisis["claimants"] if c["person"] != person]})
    if event.data["dies"]:
        return
    if world.entity(person).data.get("is_player"):
        body = load_body(world, person)
        add_injury(body, "torso", "internal", 4, world.time, "the founder's test")
        save_body(world, person, body)
    else:
        from systems.testament import set_realm
        set_realm(world, person, realm_of(world, person) - 1)


def far_founder(world, faction: int, standing: list[dict], rng) -> int | None:
    """Far away, an ambitious claimant of a great sect may try the founder's test, and passing wins (spec 10)."""
    if not great(world, faction):
        return None
    for c in sorted(standing, key=lambda c: c["person"]):
        if C.ambitious(world, c["person"]) and rng.random() < NPC_TRY and rng.random() < test_chance(world, c["person"]):
            return c["person"]
    return None


def _npc_tries(world, occurrence, stage: str) -> None:
    crisis = SC.crisis_of(occurrence)
    if not great(world, crisis["faction"]):
        return
    rng = rng_for(world.world_seed, f"founder:{occurrence.id}:{stage}")
    for c in list(SC.standing_claimants(world, crisis)):
        person = c["person"]
        if world.entity(person).data.get("is_player") or not C.ambitious(world, person) \
                or test_block(world, world.entity(occurrence.id), person) is not None or rng.random() >= NPC_TRY:
            continue
        commit(world, test_events(world, world.entity(occurrence.id), person))
        if SC.live(world, crisis["faction"]) is None:
            return


@listen("crisis_heralded")
def _mourning(world, event, event_id: int) -> None:
    occurrence = world.entity(event.data["occurrence"])
    _weddings(world, occurrence)
    _npc_tries(world, world.entity(occurrence.id), "mourning")


@listen("crisis_phase")
def _canvass(world, event, event_id: int) -> None:
    if event.data["phase"] == "canvass":
        _npc_tries(world, world.entity(event.data["occurrence"]), "canvass")


# --- marriage into the line -------------------------------------------------------------------------------

def married_line(world, crisis: dict, person: int) -> bool:
    leader = crisis.get("leader")
    spouse = spouse_of(world, person)
    return leader is not None and spouse is not None and (spouse, "child") in kin_of(world, leader)


def _weddings(world, occurrence) -> None:
    """In the mourning an unmarried claimant may wed an unmarried grown child of the late master (0.2)."""
    crisis = SC.crisis_of(occurrence)
    leader = crisis.get("leader")
    if leader is None:
        return
    rng = rng_for(world.world_seed, f"wed:{occurrence.id}")
    children = [k for k, role in kin_of(world, leader) if role == "child" and C.age_of(world, k) >= C.ADULT
                and spouse_of(world, k) is None and SC.claimant(crisis, k) is None]
    for c in crisis["claimants"]:
        person = c["person"]
        if not children or world.entity(person).data.get("is_player") or spouse_of(world, person) is not None:
            continue
        if rng.random() < MARRY_CHANCE:
            child = children.pop(0)
            commit(world, [Event("wed_for_seat", (person, child), occurrence.data["place"],
                                 {"occurrence": occurrence.id})])


@effect("wed_for_seat")
def _wed(world, event) -> None:
    _pair(world, event.actors[0], event.actors[1], "spouse")


# --- arbitration --------------------------------------------------------------------------------------------

def arbiter_of(world, faction: int) -> int | None:
    """The Murim Alliance, else the nearest orthodox sect not in crisis itself."""
    home = world.entity(faction).data.get("home")
    options = []
    for other in F.ensure_roster(world):
        o = world.entity(other)
        if other == faction or o.data.get("dissolved") or o.data.get("type") not in RIGHTEOUS:
            continue
        rank = 0 if o.data["type"] == "alliance" else 1
        options.append((rank, F.gap(home, o.data["home"]) if home and o.data.get("home") else 99, other))
    return min(options)[2] if options else None


def verdict(world, crisis: dict, standing: list[dict]) -> int:
    """Whom an arbiter names: proofs and realm only, no grudges (spec 7)."""
    weakest = min(realm_of(world, c["person"]) for c in standing)
    return max(standing, key=lambda c: (C.proof_lean(world, crisis, c) + C.REALM_LEAN * (realm_of(world, c["person"])
                                                                                       - weakest),
                                        -c["person"]))["person"]


def arbitration_events(world, occurrence, standing: list[dict], ranked: list[int]) -> list[Event]:
    """With no majority, an arbiter may rule before any trial (0.3); a proud loser may defy it (0.5)."""
    crisis, place = SC.crisis_of(occurrence), occurrence.data["place"]
    arbiter = arbiter_of(world, crisis["faction"])
    rng = rng_for(world.world_seed, f"arbiter:{occurrence.id}")
    if arbiter is None or rng.random() >= ARBITER_CHANCE:
        return []
    named = verdict(world, crisis, standing)
    loser = next(p for p in ranked if p != named)
    events = [Event("arbitrated", (named, loser), place, {"occurrence": occurrence.id, "arbiter": arbiter})]
    if SC.PROUD & set(world.entity(loser).data.get("traits", ())) and rng.random() < DEFY_CHANCE:
        return events + [Event("arbiter_defied", (loser, named), place, {"arbiter": arbiter}),
                         Event("crisis_refused", (loser, named), place, {"occurrence": occurrence.id})]
    return events + SC.settle_events(world, occurrence, named, "arbiter")


@listen("arbiter_defied")
def _defied(world, event, event_id: int) -> None:
    loser, named = event.actors
    variant = make_variant("defied_arbiter", loser, event.data["arbiter"], place=place_name(world, event.place))
    record_fact(world, loser, "defied_arbiter", event.data["arbiter"], place=event.place, source_event=event_id,
                weight=2.0, variant=variant)


# --- an outsider named heir ------------------------------------------------------------------------------

def outsider_for(world, faction: int, leader: int) -> int | None:
    """The best-known martial wanderer of the seat's region, at the late master's realm or above."""
    seat = world.entity(faction).data.get("seat")
    if seat is None:
        return None
    region = world.targets(seat, "located_in")
    towns = [t for t in world.sources(region[0], "located_in") if world.entity(t).kind == "town"] if region else []
    floor = realm_of(world, leader)
    able = [p.id for t in towns for p in people_at(world, t) if p.data.get("occupation") in WANDERERS
            and not p.data.get("is_player") and realm_of(world, p.id) >= floor and not F.memberships(world, p.id)]
    return max(able, key=lambda p: (realm_of(world, p), -p)) if able else None


@listen("died")
def _outsider_named(world, event, event_id: int) -> None:
    """A dying master with no chief disciple may name a respected outsider (0.1)."""
    victim = event.actors[-1]
    for fid, _, data in F.memberships(world, victim):
        faction = world.entity(fid)
        if data.get("role") != "leader" or faction.data.get("type") not in F.STAFFED or faction.data.get("heir"):
            continue
        if rng_for(world.world_seed, f"outsider:{fid}:{victim}").random() < OUTSIDER_CHANCE:
            chosen = outsider_for(world, fid, victim)
            if chosen is not None:
                world.update_data(fid, outsider=chosen)


def _outsider_claims(world, occurrence) -> None:
    """At a crisis's start the outsider named claims; a will read out names them."""
    crisis = SC.crisis_of(occurrence)
    outsider = world.entity(crisis["faction"]).data.get("outsider")
    if outsider is None:
        return
    world.update_data(crisis["faction"], outsider=None)
    if not alive(world, outsider) or SC.claimant(crisis, outsider) is not None:
        return
    will = crisis.get("will") or {}
    if will.get("state") == "read":
        will = {**will, "names": outsider}
    world.update_data(occurrence.id, data={**crisis, "will": will,
                                           "claimants": crisis["claimants"] + [{"person": outsider, "kind": "outsider"}]})


P.BEGUN_HOOKS.append(_outsider_claims)
world_clock.SEASON_HOOKS.append(teaching_events)
