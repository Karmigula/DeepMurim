"""Physicians, famous doctors, the healer and the poisoner for hire (phase 5c spec 5.1-5.3).

Every town has a physician (a seeded person, made the first time they are paid): they treat a wound for silver
so it heals three times as fast, cure a weak poison, and for five silver read the body and name its poisons.
Famous doctors, one to each block of eight regions, wander; asking after one in a town tells where they were
last seen. They cure what no physician can, on their own terms. The player may treat the sick, with a fitting
pill or with herbs and a roll, and five healings in a town make them its healer; an unorthodox soul who believes
the player knows poison may offer silver for a poisoning.
"""

import systems.alchemy as A
import systems.herbs as H
import systems.lives as lives
import systems.pills as P
import systems.toxins as X
from systems import factions as F
from systems.attitude import attitude, is_bandit
from systems.beliefs import apparent_to, knowledge_of
from systems.bodies import load_body, save_body
from systems.facts import make_variant, place_name, record_fact
from systems.founding import make_person
from systems.purse import silver_of
from systems.reputation import reputation
from world.body import body_of, heal_watches, settle
from world.events import Event, Witness, effect, listen
from world.gen.materialize import ensure_town, people_at, region_label, town_label
from world.gen.names import person_name
from world.gen.region import region_spec
from world.seed import rng_for

TREAT_PRICE, CURE_PRICE, READ_PRICE = 10, 20, 5  # x severity squared, x grade squared, flat
CURE_GRADE = 3             # the strongest poison a town physician can cure
FASTER = 3
BLOCK = (4, 2)             # a famous doctor's wandering ground: four regions by two
EPITHETS = ("Ghost", "Divine", "Poison-Eating", "Needle", "Hundred-Herb", "Crane-Hand", "Sleepless", "Laughing")
WHIMS = ("gold", "task", "righteous", "eccentric")
DOCTOR_GOLD = 1000
DOCTOR_CURES = ("poison", "meridian", "injury")
CURE_HOOKS: dict = {}      # what else a famous doctor cures: name -> (block(world, person), apply(world, person))
HEAL_ROLL, HEAL_PER_LEVEL, HEAL_BOUNDS = 0.3, 0.1, (0.1, 0.9)
HEALING_ELEMENTS = frozenset({"wood", "earth", "water"})
HEALER_AT = 5
PATIENT_CHANCE = 0.2
UNFIT = frozenset({"hostile", "hateful"})
POISON_FAME = frozenset({"poison_body", "poisoner", "poisoned_for_hire"})
CONTRACT_OFFER = 0.3       # chance a fitting soul offers, once a season
CONTRACT_PAY = (100, 400)
CONTRACT_DAYS = 60
FIND_CHANCE = 0.15         # a hired poisoning traced to its poisoner


def _pay(world, person: int, amount: int, to: int | None = None) -> None:
    world.update_data(person, silver=silver_of(world, person) - amount)
    if to is not None:
        world.update_data(to, silver=silver_of(world, to) + amount)


# --- the town physician -------------------------------------------------------------------------------------

def physician_path(town: int) -> str:
    return f"physician:{town}"


def physician(world, town: int) -> int:
    """The town's physician, made the first time they are paid (never for a menu: reads never write)."""
    found = world.entity_by_seed(physician_path(town))
    if found is not None:
        return found.id
    return make_person(world, physician_path(town), town, occupation="physician", age=rng_for(
        world.world_seed, f"{physician_path(town)}/age").randint(40, 70))


def treatable(body, now: int) -> list:
    return sorted((i for i in body.injuries if not i.permanent and i.heals_at and i.heals_at > now),
                  key=lambda i: (-i.severity, i.id))


def treat_price(severity: int) -> int:
    return TREAT_PRICE * severity ** 2


def cure_price(grade: int) -> int:
    return CURE_PRICE * grade ** 2


def clinic_block(world, place) -> str | None:
    entity = world.entity(place)
    return None if entity is not None and entity.kind == "town" else "There is no physician here."


def treat_block(world, person: int, injury_id: int, place) -> str | None:
    if clinic_block(world, place):
        return clinic_block(world, place)
    injury = next((i for i in treatable(load_body(world, person), world.time) if i.id == injury_id), None)
    if injury is None:
        return "There is nothing there a physician can hasten."
    if silver_of(world, person) < treat_price(injury.severity):
        return f"The physician asks {treat_price(injury.severity)} silver."
    return None


def treat_events(world, person: int, injury_id: int, place) -> list[Event]:
    injury = next(i for i in treatable(load_body(world, person), world.time) if i.id == injury_id)
    return [Event("physician_treated", (person, physician(world, place)), place, {"injury": injury_id, "location": injury.location,
                                                          "price": treat_price(injury.severity)})]


@effect("physician_treated")
def _treated(world, event) -> None:
    person, d = event.actors[0], event.data
    _pay(world, person, d["price"], event.actors[1])
    body = load_body(world, person)
    for injury in body.injuries:
        if injury.id == d["injury"] and injury.heals_at and injury.heals_at > world.time:
            injury.heals_at = world.time + max(1, (injury.heals_at - world.time) // FASTER)
    save_body(world, person, body)


def curable(body) -> int | None:
    """The worst poison a town physician can cure in this body, or None."""
    grades = [p["grade"] for p in body.poisons if p["grade"] <= CURE_GRADE]
    return max(grades) if grades else None


def cure_block(world, person: int, place) -> str | None:
    if clinic_block(world, place):
        return clinic_block(world, place)
    body = load_body(world, person)
    grade = curable(body)
    if grade is None:
        return "The physician can cure no poison of yours." if body.poisons else "There is no poison in you."
    if silver_of(world, person) < cure_price(grade):
        return f"The physician asks {cure_price(grade)} silver."
    return None


def cure_events(world, person: int, place) -> list[Event]:
    grade = curable(load_body(world, person))
    return [Event("physician_cured", (person, physician(world, place)), place, {"grade": grade,
                                                                                 "price": cure_price(grade)})]


@effect("physician_cured")
def _cured(world, event) -> None:
    person, d = event.actors[0], event.data
    _pay(world, person, d["price"], event.actors[1])
    X.cure(world, person, d["grade"])


def read_block(world, person: int, place) -> str | None:
    if clinic_block(world, place):
        return clinic_block(world, place)
    if silver_of(world, person) < READ_PRICE:
        return f"The physician asks {READ_PRICE} silver."
    return None


def read_events(world, person: int, place) -> list[Event]:
    return [Event("body_read", (person, physician(world, place)), place, {"price": READ_PRICE})]


@effect("body_read")
def _read(world, event) -> None:
    person = event.actors[0]
    _pay(world, person, event.data["price"], event.actors[1])
    body = load_body(world, person)
    body.poisons = [{**p, "named": True} for p in body.poisons]
    save_body(world, person, body)


# --- famous doctors -------------------------------------------------------------------------------------------

def block_of(x: int, y: int) -> tuple[int, int]:
    return x // BLOCK[0], y // BLOCK[1]


def doctor_path(block) -> str:
    return f"doctor:{block[0]}:{block[1]}"


def doctor_spec(world, block) -> dict:
    """A block's famous doctor, from the seed: name, title, whim and home region."""
    rng = rng_for(world.world_seed, f"{doctor_path(block)}/spec")
    home = (block[0] * BLOCK[0] + rng.randrange(BLOCK[0]), block[1] * BLOCK[1] + rng.randrange(BLOCK[1]))
    surname, given = person_name(rng_for(world.world_seed, doctor_path(block)))  # as make_person names them
    return {"name": f"{surname} {given}", "title": f"the {rng.choice(EPITHETS)} Doctor of {region_label(world, *home)}",
            "whim": rng.choice(WHIMS), "home": list(home), "block": list(block)}


def seen_at(world, block, season: int) -> tuple[int, int, int]:
    """(x, y, town index) where the block's doctor is this season: they wander their block."""
    rng = rng_for(world.world_seed, f"{doctor_path(block)}:{season}")
    x, y = block[0] * BLOCK[0] + rng.randrange(BLOCK[0]), block[1] * BLOCK[1] + rng.randrange(BLOCK[1])
    return x, y, rng.randrange(region_spec(world.world_seed, x, y).town_count)


def ask_events(world, person: int, place) -> list[Event]:
    here = world.entity(place).data
    block = block_of(here["x"], here["y"])
    season = lives.current_season(world)
    x, y, i = seen_at(world, block, season)
    return [Event("asked_doctor", (person,), place, {"block": list(block), "season": season, "at": [x, y, i],
                                                     "town": town_label(world, x, y, i)})]


@effect("asked_doctor")
def _asked(world, event) -> None:
    """The doctor of this block is made the first time anyone asks, and is where they were last seen."""
    person, d = event.actors[0], event.data
    town = ensure_town(world, *d["at"])
    doctor = ensure_doctor(world, tuple(d["block"]), town)
    world.unrelate(doctor, "located_in")
    world.relate(doctor, town, "located_in")
    seen = dict(world.entity(person).data.get("doctors_seen") or {})
    seen[doctor_path(d["block"])] = {"town": d["town"], "season": d["season"], "doctor": doctor}
    world.update_data(person, doctors_seen=seen)


@listen("asked_doctor")
def _seen_news(world, event, event_id: int) -> None:
    """Where a famous doctor was seen is a rumour: the asker hears it, and so does the town (spec 8)."""
    doctor = world.entity(world.entity(event.actors[0]).data["doctors_seen"][doctor_path(event.data["block"])]["doctor"])
    variant = make_variant("doctor_seen", doctor.id, None, place=event.data["town"])
    variant.update(title=doctor.data["doctor"]["title"])
    record_fact(world, doctor.id, "doctor_seen", None, place=event.place, source_event=event_id, weight=0.5,
                variant=variant)


def ensure_doctor(world, block, town: int) -> int:
    found = world.entity_by_seed(doctor_path(block))
    if found is not None:
        return found.id
    spec = doctor_spec(world, block)
    return make_person(world, doctor_path(block), town, occupation="famous doctor", realm="first-rate",
                       age=rng_for(world.world_seed, f"{doctor_path(block)}/age").randint(55, 95),
                       doctor={k: spec[k] for k in ("title", "whim", "home", "block")})


def doctors_here(world, place) -> list[int]:
    return [p.id for p in people_at(world, place) if p.data.get("doctor") and not p.data.get("dead")]


def doctor_cures(world, person: int) -> list[str]:
    """What a famous doctor could cure in this person now."""
    body = load_body(world, person)
    out = []
    if body.poisons:
        out.append("poison")
    if any(m.state in ("damaged", "severed") for m in body.meridians.values()):
        out.append("meridian")
    if any(i.permanent for i in body.injuries):
        out.append("injury")
    for name, (block, _) in sorted(CURE_HOOKS.items()):
        if block(world, person):
            out.append(name)
    return out


def terms_block(world, person: int, doctor: int, place) -> str | None:
    """Whether the doctor will treat this person on their terms (spec 5.2)."""
    whim = world.entity(doctor).data["doctor"]["whim"]
    if whim == "gold" and silver_of(world, person) < DOCTOR_GOLD:
        return f"The doctor asks {DOCTOR_GOLD} silver."
    if whim == "task" and not thousand_year_herb(world, person):
        return "The doctor asks a thousand-year herb."
    if whim == "righteous" and not orthodox(world, person, place):
        return "The doctor treats only the orthodox."
    if whim == "eccentric" and doctor not in (world.entity(person).data.get("go_won") or []):
        return "The doctor treats only one who beats them at go."
    return None


def thousand_year_herb(world, person: int) -> int | None:
    return next((h.id for h in H.herbs_of(world, person) if H.herb_info(h)[1] >= 3), None)


def orthodox(world, person: int, place) -> bool:
    dark = any(world.entity(f).data.get("type") in F.DARK and d.get("status", "member") == "member"
               for f, _, d in F.memberships(world, person))
    return not dark and reputation(world, place, apparent_to(world, place, person)).path != "ruthless"


def go_events(world, person: int, doctor: int, place) -> list[Event]:
    """A game of go with the eccentric doctor: comprehension against their wit, once a day."""
    wit = load_body(world, person).physique.get("comprehension", 5)
    roll = rng_for(world.world_seed, f"go:{doctor}:{person}:{world.time // 4}").random()
    return [Event("go_played", (person, doctor), place, {"won": roll < wit / 20})]


@effect("go_played")
def _go(world, event) -> None:
    person, doctor = event.actors
    if event.data["won"]:
        world.update_data(person, go_won=(world.entity(person).data.get("go_won") or []) + [doctor])


def doctor_events(world, person: int, doctor: int, what: str, place) -> list[Event]:
    whim = world.entity(doctor).data["doctor"]["whim"]
    return [Event("doctor_cured", (person, doctor), place, {
        "what": what, "whim": whim, "price": DOCTOR_GOLD if whim == "gold" else 0,
        "herb": thousand_year_herb(world, person) if whim == "task" else None})]


@effect("doctor_cured")
def _doctor_cured(world, event) -> None:
    person, doctor = event.actors
    d = event.data
    if d["price"]:
        _pay(world, person, d["price"], doctor)
    if d["herb"] is not None:
        H.spend(world, person, [d["herb"]])
    if d["what"] in CURE_HOOKS:
        CURE_HOOKS[d["what"]][1](world, person)
        return
    body = load_body(world, person)
    if d["what"] == "poison":
        body.poisons = []
        body.flags = [f for f in body.flags if f != X.POISONED_TO_DEATH]
    elif d["what"] == "meridian":
        for meridian in body.meridians.values():
            if meridian.state in ("damaged", "severed"):
                meridian.state, meridian.heals_at = "open", None
    elif d["what"] == "injury":
        worst = max((i for i in body.injuries if i.permanent), key=lambda i: (i.severity, -i.id), default=None)
        if worst is not None:
            worst.permanent, worst.heals_at = False, world.time + heal_watches(worst.severity, body)
    save_body(world, person, body)
    if d["what"] == "poison":
        X._forget_if_clean(world, person, body)


# --- the player as healer ---------------------------------------------------------------------------------------

def ailment(world, npc: int) -> str | None:
    """What ails someone, from their stored body (never rolled for asking): poison, or a wound, or None."""
    entity = world.entity(npc)
    stored = body_of(entity)
    if stored is None or entity.data.get("dead") or entity.data.get("beast"):
        return None
    body = settle(stored, world.time)
    if body.poisons:
        return "poison"
    return "wound" if treatable(body, world.time) else None


def remedy(world, person: int, npc: int) -> tuple[str, list[int]] | None:
    """How the player would treat them: ("pill", [pill]) or ("herbs", [two herbs]), or None."""
    what = ailment(world, npc)
    if what is None:
        return None
    body = settle(body_of(world.entity(npc)), world.time)
    for pill in P.pills_of(world, person):
        kind, grade = P.effect_of(pill), P.grade_of(pill)
        if what == "wound" and kind == "healing":
            return "pill", [pill.id]
        if what == "poison" and kind == "antidote" and grade >= max(p["grade"] for p in body.poisons):
            return "pill", [pill.id]
    herbs = [h.id for h in H.herbs_of(world, person) if H.known(world, person, H.herb_info(h)[0])
             and H.props(H.herb_info(h)[0])["element"] in HEALING_ELEMENTS
             and H.props(H.herb_info(h)[0])["toxicity"] <= 1]
    return ("herbs", herbs[:2]) if len(herbs) >= 2 else None


def heal_block(world, person: int, npc: int, place) -> str | None:
    if place not in world.targets(npc, "located_in"):
        return "They are not here."
    if ailment(world, npc) is None:
        return "Nothing ails them."
    if attitude(world, npc, apparent_to(world, npc, person)).word in UNFIT:
        return "They will not let you near them."
    if remedy(world, person, npc) is None:
        return "You have nothing fit to treat them with."
    return None


def heal_chance(world, person: int) -> float:
    return max(HEAL_BOUNDS[0], min(HEAL_BOUNDS[1], HEAL_ROLL + HEAL_PER_LEVEL * A.level(world, person)))


def heal_events(world, person: int, npc: int, place) -> list[Event]:
    how, items = remedy(world, person, npc)
    roll = rng_for(world.world_seed, f"heal:{person}:{npc}:{world.time}").random()
    success = how == "pill" or roll < heal_chance(world, person)
    witnesses = (Witness(npc, "grateful", 0.3),) if success else ()
    return [Event("healed", (person, npc), place, {"how": how, "items": items, "ailment": ailment(world, npc),
                                                    "success": success}, witnesses=witnesses)]


@effect("healed")
def _healed(world, event) -> None:
    person, npc = event.actors
    d = event.data
    if d["how"] == "pill":
        world.unrelate(person, "owns", d["items"][0])
        world.update_data(d["items"][0], used=True)
    else:
        H.spend(world, person, d["items"])
    if not d["success"]:
        return
    body = load_body(world, npc)
    if d["ailment"] == "poison":
        body.poisons, body.flags = [], [f for f in body.flags if f != X.POISONED_TO_DEATH]
    else:
        for injury in body.injuries:
            if not injury.permanent and injury.heals_at and injury.heals_at > world.time:
                injury.heals_at = world.time
    save_body(world, npc, body)
    X._forget_if_clean(world, npc, body)
    if event.place is not None and world.entity(event.place).kind == "town":
        counts = dict(world.entity(person).data.get("healings") or {})
        counts[str(event.place)] = counts.get(str(event.place), 0) + 1
        world.update_data(person, healings=counts)


@listen("healed")
def _healed_news(world, event, event_id: int) -> None:
    if not event.data["success"]:
        return
    person, npc = event.actors
    record_fact(world, person, "healed", npc, place=event.place, source_event=event_id, weight=1.0,
                variant=make_variant("healed", person, npc, place=place_name(world, event.place)))


def healer_of(world, person: int) -> list[int]:
    """The towns where the player has healed five: each calls them its healer."""
    return sorted(int(t) for t, n in (world.entity(person).data.get("healings") or {}).items() if n >= HEALER_AT)


def patient_events(world, person: int, town: int) -> list[Event]:
    """A known healer is sometimes brought someone sick (spec 5.3): made on the spot, hurt or poisoned."""
    if town not in healer_of(world, person):
        return []
    day = world.time // 4
    if world.entity_by_seed(f"patient:{person}:{town}:{day}") is not None:
        return []  # one brought a day
    rng = rng_for(world.world_seed, f"patient:{person}:{town}:{day}")
    if rng.random() >= PATIENT_CHANCE:
        return []
    return [Event("patient_brought", (person,), town, {"path": f"patient:{person}:{town}:{day}",
                                                       "poisoned": rng.random() < 0.3})]


@effect("patient_brought")
def _patient(world, event) -> None:
    d = event.data
    sick = make_person(world, d["path"], event.place)
    body = load_body(world, sick)
    if d["poisoned"]:
        X.add_poison(world, sick, body, 2, 12, "a bad well")
    else:
        from world.body import add_injury
        add_injury(body, "torso", "internal", 2, world.time, "a fever")
    save_body(world, sick, body)
    world.update_data(event.actors[0], patient=sick)


# --- poison for hire --------------------------------------------------------------------------------------------

def unorthodox(world, npc: int) -> bool:
    entity = world.entity(npc)
    return is_bandit(entity) or any(world.entity(f).data.get("type") in F.DARK and d.get("status", "member") == "member"
                                    for f, _, d in F.memberships(world, npc))


def knows_you_poison(world, npc: int, person: int) -> bool:
    seen = apparent_to(world, npc, person)
    return any(f.predicate in POISON_FAME and b.variant.get("actor") in (person, seen)
               for b, f in knowledge_of(world, npc))


def contract_offer(world, npc: int, person: int) -> dict | None:
    """A poisoning this client would pay for, once a season: a mark in their town, and the silver."""
    if world.entity(person).data.get("contract") or not unorthodox(world, npc) or not knows_you_poison(world, npc, person):
        return None
    season = lives.current_season(world)
    rng = rng_for(world.world_seed, f"contract:{npc}:{person}:{season}")
    if rng.random() >= CONTRACT_OFFER:
        return None
    town = next(iter(world.targets(npc, "located_in")), None)
    marks = sorted(p.id for p in people_at(world, town) if p.id not in (npc, person) and lives.simulated(p)) \
        if town is not None else []
    if not marks:
        return None
    return {"client": npc, "target": rng.choice(marks), "silver": rng.randint(*CONTRACT_PAY)}


def contract_events(world, person: int, offer: dict, place) -> list[Event]:
    return [Event("contract_taken", (person, offer["client"], offer["target"]), place,
                  {"silver": offer["silver"], "deadline": world.time + CONTRACT_DAYS * 4})]


@effect("contract_taken")
def _taken(world, event) -> None:
    person, client, target = event.actors
    world.update_data(person, contract={"client": client, "target": target, "silver": event.data["silver"],
                                        "deadline": event.data["deadline"], "done": False})


def contract_poison_block(world, person: int, target: int, place) -> str | None:
    from systems.scheming import poisons_of
    contract = world.entity(person).data.get("contract")
    if not contract or contract["target"] != target or contract["done"]:
        return "No one pays you to poison them."
    if place not in world.targets(target, "located_in"):
        return "They are not here."
    if not poisons_of(world, person):
        return "You carry no poison."
    return None


def contract_poison_events(world, person: int, target: int, place) -> list[Event]:
    from systems.scheming import poison_grade, poisons_of
    vial = max(poisons_of(world, person), key=lambda i: (poison_grade(world.entity(i)), -i))
    grade = poison_grade(world.entity(vial))
    found = rng_for(world.world_seed, f"contract_found:{person}:{target}").random() < FIND_CHANCE
    events = [Event("contract_poisoned", (person, target), place, {"vial": vial, "grade": grade, "found": found})]
    if grade >= X.LETHAL_GRADE:
        events.append(Event("died", (target, target), place, {"cause": "illness", "world": True,
                                                              "poisoned_by": person}))
    return events


@effect("contract_poisoned")
def _poisoned(world, event) -> None:
    person, target = event.actors
    d = event.data
    world.unrelate(person, "owns", d["vial"])
    world.update_data(d["vial"], used=True)
    if d["grade"] < X.LETHAL_GRADE:
        X.poison(world, target, d["grade"], d["grade"] * P.POISON_STRENGTH, "a poisoned cup")
    contract = world.entity(person).data.get("contract")
    if contract and contract["target"] == target:
        world.update_data(person, contract={**contract, "done": True})


@listen("contract_poisoned")
def _traced(world, event, event_id: int) -> None:
    if not event.data["found"]:
        return
    person, target = event.actors
    record_fact(world, person, "poisoned_for_hire", target, place=event.place, source_event=event_id, weight=3.0,
                variant=make_variant("poisoned_for_hire", person, target, place=place_name(world, event.place)))


def fee_block(world, person: int, client: int) -> str | None:
    contract = world.entity(person).data.get("contract")
    if not contract or contract["client"] != client:
        return "They owe you nothing."
    if not contract["done"]:
        return "The job is not done."
    return None


def fee_events(world, person: int, client: int, place) -> list[Event]:
    contract = world.entity(person).data["contract"]
    return [Event("contract_paid", (person, client), place, {"silver": min(contract["silver"],
                                                                           silver_of(world, client))})]


@effect("contract_paid")
def _fee(world, event) -> None:
    person, client = event.actors
    world.update_data(client, silver=silver_of(world, client) - event.data["silver"])
    world.update_data(person, silver=silver_of(world, person) + event.data["silver"], contract=None)


def contract_lapsed(world, person: int) -> bool:
    """A contract past its deadline, or whose client or mark died by other hands, is void."""
    contract = world.entity(person).data.get("contract")
    if not contract:
        return False
    client, target = world.entity(contract["client"]), world.entity(contract["target"])
    if client is None or client.data.get("dead"):
        return True
    if not contract["done"] and (world.time > contract["deadline"] or target is None or target.data.get("dead")):
        return True
    return False


def void_events(world, person: int, place) -> list[Event]:
    return [Event("contract_void", (person,), place, {})]


@effect("contract_void")
def _void(world, event) -> None:
    world.update_data(event.actors[0], contract=None)
