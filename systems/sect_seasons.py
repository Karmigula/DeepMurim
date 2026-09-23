"""The seasonal catch-up for your sect (phase 3c spec 6): one season's events at a time, all seeded.

The engine commits each season before asking for the next, so a season always
sees the world its predecessor left, and one call for eight seasons gives the
same sect as eight calls for one.
"""

import systems.founding as founding
import systems.sect as sect_mod
from systems import factions as F
from systems import halls
from systems.attitude import attitude
from systems.beliefs import apparent_to
from systems.bodies import load_body, save_body
from systems.combat_core import INTENTS
from systems.duel import best_art, fighter_for
from systems.duel_sim import simulate
from systems.facts import make_variant, place_name, record_fact
from systems.membership import left_events
from systems.realms import add_energy, breakthrough_chance, realm_index
from systems.reputation import reputation
from systems.time import format_season_year
from world.body import add_injury
from systems.techniques import teach
from world.events import Event, effect, listen
from world.gen.materialize import region_of
from world.seed import rng_for

SEASON = 360
MAX_SEASONS = 8
LAND_INCOME = {"village": 20, "town": 40, "city": 80}
PROTECTION = 10
DUTY_PAY, ALLY_GIFT = 20, 30
INJURY, DEATH_ON_DUTY, DUTY_INJURY = 0.08, 0.05, 0.3
GATE_BASE, GATE_HOSTILE, GATE_DEATH = 0.15, 0.25, 0.1
DESERT_BELOW, DESERT_CHANCE = 25, 0.5
RECRUITS = {"unknown": 0, "little known": 1, "known": 1, "renowned": 2, "famous": 3}
PATH_TRAITS = {"righteous": {"kind", "honest"}, "ruthless": {"cunning", "hot-tempered"}}


def _knows_sect_art(world, person: int, arts: list[int]) -> bool:
    return bool(set(arts) & {t for t, _, _ in world.relations_from(person, "knows")})


def _hostile(world, sect: int, people: list[int] | None = None) -> list[int]:
    if people is None:
        people = sect_mod.members(world, sect)
    # only the founder (who may wear masks) and members who did harm can move a stance
    roster = [world.entity(sect).data["founder"],
              *(p for p in people if any(f.predicate in sect_mod.HARM for f in world.facts(subject=p)))]
    return [f for f in F.ensure_roster(world) if sect_mod.sect_stance(world, f, sect, roster) <= -0.5]


def _challenger(world, sect: int, hostile: list[int], rng, n: int) -> int:
    for other in hostile:
        staff = halls.staff_at(world, other, halls.seat_of(world, other), roles=("disciple",))
        if staff:
            return rng.choice(sorted(staff))
    seat = world.entity(sect).data["seat"]  # a wanderer lives on the roads, not at your seat
    return founding.make_person(world, f"sect:{sect}:gate:{n}", region_of(world, seat).id, occupation="wandering swordsman",
                                realm=world.entity(world.entity(sect).data["founder"]).data.get("realm", "mortal"))


def _fight(world, defender: int, challenger: int, rng) -> bool:
    mine, theirs = best_art(world, defender), best_art(world, challenger)
    a = fighter_for(world, defender, mine.technique.id if mine else None)
    b = fighter_for(world, challenger, theirs.technique.id if theirs else None)
    result, _ = simulate(a, b, lambda r, history: r.choice(INTENTS), rng)
    return result == "player"


def season_events(world, player: int, sect: int) -> list[Event] | None:
    """The events of the next due season of the player's sect, or None if none is due."""
    data = world.entity(sect).data
    if data.get("dissolved") or world.time - data["last_tick"] < SEASON:
        return None
    n = data["last_tick"] // SEASON
    rng = rng_for(world.world_seed, f"sect:{sect}:season:{n}")
    seat, end = data["seat"], data["last_tick"] + SEASON
    roles = {p: F.membership(world, p, sect)[1].get("role") for p in F.members_of(world, sect)}
    people = sorted(p for p, r in roles.items() if r in ("disciple", "elder"))
    disciples = [p for p in people if roles[p] == "disciple"]
    elders = [p for p in people if roles[p] == "elder"]
    cache: dict = {}

    def who(person: int):  # one read per person per season; the season changes nothing until it commits
        if person not in cache:
            cache[person] = world.entity(person)
        return cache[person]
    built_now = [b for b, v in sorted(data.get("buildings", {}).items()) if not v["built"] and v["done_at"] <= end]
    has = {b for b, v in data.get("buildings", {}).items() if v["built"]} | set(built_now)

    # duties
    won, duty_hurt, died = [], [], []
    for person in people:
        if not who(person).data.get("on_duty"):
            continue
        realm = realm_index(who(person).data.get("realm", "mortal"))
        if rng.random() < 0.5 + 0.1 * realm:
            won.append(person)
        else:
            roll = rng.random()
            if roll < DEATH_ON_DUTY:
                died.append(person)
            elif roll < DEATH_ON_DUTY + DUTY_INJURY:
                duty_hurt.append(person)

    # money
    rep = reputation(world, seat, apparent_to(world, seat, player))
    allies = len(world.targets(sect, "pact"))
    protection = PROTECTION if rep.renown >= 2 and rep.path != "ruthless" else 0
    income = LAND_INCOME.get(world.entity(seat).data.get("kind"), 20) + DUTY_PAY * len(won) + ALLY_GIFT * allies + protection
    upkeep = 5 * len(disciples) + 10 * len(elders) + sum(sect_mod.BUILDINGS[b][1] for b in has)
    treasury = data["treasury"] + income - upkeep
    unpaid = treasury < 0
    treasury = max(0, treasury)

    # growth
    present = [p for p in people if p not in died and not who(p).data.get("on_duty")]
    growth = {}
    for person in present:
        talent = who(person).data.get("talent", 1.0)
        years = 0.25 * talent * (1.5 if "training_yard" in has else 1.0) \
            * (1.2 if _knows_sect_art(world, person, data.get("arts", [])) else 1.0)
        body = load_body(world, person)  # a fresh copy; nothing is saved here
        add_energy(body, years)
        breakthrough = body.bottleneck and rng.random() < breakthrough_chance(body, True)
        growth[str(person)] = {"years": round(years, 4), "breakthrough": bool(breakthrough)}

    # the library: present elders teach each present disciple one sect art they lack
    taught = {}
    if "library" in has:
        teachers = [e for e in elders if e in present]
        for person in (p for p in disciples if p in present):
            mine = {t for t, _, _ in world.relations_from(person, "knows")}
            for art in data.get("arts", []):
                elder = next((e for e in teachers if art in {t for t, _, _ in world.relations_from(e, "knows")}), None)
                if art not in mine and elder is not None:
                    taught[str(person)] = [art, elder]
                    break

    # injuries
    chance = INJURY * (0.5 if "infirmary" in has else 1.0)
    injured = [p for p in present if rng.random() < chance] + duty_hurt

    # loyalty and desertion
    loyalty, deserters = {}, []
    for person in people:
        if person in died:
            continue
        entity = who(person)
        value = entity.data.get("loyalty", 50) + (-15 if unpaid else 5)
        wanted = PATH_TRAITS.get(data["path"])
        if wanted is not None:
            value += 5 if wanted & set(entity.data.get("traits", ())) else -10
        word = attitude(world, person, player).word
        value += 5 if word == "warm" else -10 if word in ("wary", "hostile", "hateful") else 0
        value = max(0, min(100, value))
        loyalty[str(person)] = value
        if value < DESERT_BELOW and rng.random() < DESERT_CHANCE:
            deserters.append(person)

    # recruits
    leaving = set(died) | set(deserters)
    room = sect_mod.MAX_DISCIPLES - len([d for d in disciples if d not in leaving])
    rolls = RECRUITS.get(rep.word, 0) + (1 if "guest_hall" in has else 0)
    paths = [f"sect:{sect}:recruit:{n}:{i}" for i in range(rolls) if rng.random() < 0.5][:max(0, room)]
    recruits = [(found.id if (found := world.entity_by_seed(path)) else founding.make_person(world, path, seat))
                for path in paths]  # made now, so the season's event can name them as actors

    # the gate
    hostile = _hostile(world, sect, people)
    gate_chance = (GATE_BASE + (GATE_HOSTILE if hostile else 0.0)) * (0.5 if "walls" in has else 1.0)
    gate = None
    power = data["power"] + 2 * len(won)
    if rng.random() < gate_chance:
        challenger = _challenger(world, sect, hostile, rng, n)
        if seat in world.targets(player, "located_in"):
            home = (world.targets(challenger, "located_in") or [region_of(world, seat).id])[0]
            gate = {"challenger": challenger, "deferred": True, "won": None, "defenders": [], "fallen": [], "home": home}
        else:
            standing_by = sorted((p for p in present if p not in deserters),
                                 key=lambda p: -realm_index(who(p).data.get("realm", "mortal")))
            defenders = standing_by[:2 if "walls" in has else 1]
            fallen, won_gate = [], False
            for defender in defenders:
                if _fight(world, defender, challenger, rng):
                    won_gate = True
                    break
                fallen.append(defender)
                if rng.random() < GATE_DEATH:
                    died.append(defender)
            gate = {"challenger": challenger, "deferred": False, "won": won_gate, "defenders": defenders, "fallen": fallen}
            power += 5 if won_gate else -5

    names = lambda ids: ", ".join(world.entity(p).name for p in ids)  # noqa: E731
    parts = [f"{'+' if treasury - data['treasury'] >= 0 else ''}{treasury - data['treasury']} silver"]
    rises = [p for p, g in growth.items() if g["breakthrough"]]
    if rises:
        parts.append(f"{names([int(p) for p in rises])} broke through")
    if taught:
        parts.append(f"{len(taught)} learned the sect's arts from the elders")
    if recruits:
        parts.append(f"{len(recruits)} recruit{'s' if len(recruits) > 1 else ''} arrived")
    if deserters:
        parts.append(f"{names(deserters)} deserted")
    if died:
        parts.append(f"{names(died)} died")
    if gate and not gate["deferred"]:
        parts.append("the gate was held" if gate["won"] else "the gate was breached")
    when = format_season_year(end)
    line = f"{when[:1].upper()}{when[1:]}: " + "; ".join(parts) + "."
    summary = {"sect": sect, "season": n, "end": end, "income": income, "upkeep": upkeep, "unpaid": unpaid,
               "treasury_after": treasury, "built": built_now, "growth": growth, "injured": sorted(set(injured)),
               "loyalty": loyalty, "recruits": recruits, "gate": gate, "power_after": max(0, power),
               "duties_won": won, "line": line, "taught": taught, "infirmary": "infirmary" in has}
    # the founder hears of everyone the season touched, so the ledger never names a stranger
    events = [Event("sect_season", tuple(dict.fromkeys((player, *people, *recruits))), seat, summary)]
    events += [Event("died", (p, p), seat, {"cause": "duty" if p not in (gate or {}).get("fallen", []) else "gate"})
               for p in died]
    for person in deserters:
        events += left_events(world, person, sect, seat, "deserter")
    remaining = [p for p in people if p not in died and p not in deserters]
    if not remaining and not recruits:
        events.append(Event("sect_dissolved", (player,), seat, {"sect": sect, "reason": "empty"}))
    return events


@effect("sect_season")
def _season(world, event) -> None:
    d = event.data
    sect = d["sect"]
    data = world.entity(sect).data
    buildings = {b: ({**v, "built": True} if b in d["built"] else v) for b, v in data.get("buildings", {}).items()}
    chronicle = [*data.get("chronicle", []), d["line"]][-12:]
    world.update_data(sect, treasury=d["treasury_after"], power=d["power_after"], buildings=buildings,
                      last_tick=data["last_tick"] + SEASON, chronicle=chronicle)
    for person, value in d["loyalty"].items():
        world.update_data(int(person), loyalty=value)
    for person, g in d["growth"].items():
        body = load_body(world, int(person))
        if d["infirmary"]:
            body.injuries = [i for i in body.injuries if i.permanent]
        add_energy(body, g["years"])
        if g["breakthrough"] and body.bottleneck:
            body.realm += 1
            body.bottleneck = False
        save_body(world, int(person), body)
    for person in d["injured"]:
        body = load_body(world, person)
        add_injury(body, "torso", "bruise", 2, world.time, "the hard life of the sect")
        save_body(world, person, body)
    gate = d["gate"] or {}
    for person in gate.get("fallen", []):
        body = load_body(world, person)
        add_injury(body, "torso", "cut", 3, world.time, f"defending the gate against {world.entity(gate['challenger']).name}")
        save_body(world, person, body)
    for person, (art, elder) in d.get("taught", {}).items():
        teach(world, int(person), art, source="sect", teacher=elder)
    for person in d["recruits"]:
        founding.enrol(world, person, sect, 50)
    visitors = {}
    for person, home in data.get("visitors", {}).items():  # last season's challenger goes home
        if not world.entity(int(person)).data.get("dead") and world.targets(int(person), "located_in") == [data["seat"]]:
            world.unrelate(int(person), "located_in")
            world.relate(int(person), home, "located_in")
    if gate.get("deferred"):
        visitors[str(gate["challenger"])] = gate["home"]
    world.update_data(sect, visitors=visitors)
    if gate.get("deferred"):
        world.unrelate(gate["challenger"], "located_in")
        world.relate(gate["challenger"], data["seat"], "located_in")
        world.update_data(event.actors[0], gate_challenger=gate["challenger"])


@listen("sect_season")
def _gate_fact(world, event, event_id: int) -> None:
    gate = event.data["gate"] or {}
    if gate.get("deferred") or gate.get("won") is None:
        return
    sect = event.data["sect"]
    predicate = "defended_gate" if gate["won"] else "gate_breached"
    record_fact(world, sect, predicate, gate["challenger"], place=event.place, source_event=event_id, weight=1.0,
                variant=make_variant(predicate, sect, gate["challenger"], place=place_name(world, event.place)))
