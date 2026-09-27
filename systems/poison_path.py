"""The poison path, the Myriad Poison Body, venomous beasts and tempering baths (phase 5b spec 4.3-4.6).

A practitioner of a poison art (element `poison`, mastery 0.3 or more) turns part of any poison they take into qi,
and the rest into venom in the body; at 60 venom the body turns: a Myriad Poison Body, immune to lesser poisons,
its blood a venom to whoever strikes it bare-handed. Their own strikes leave poison. Poison arts are bought from
an unorthodox clan's keeper. A great venomous beast may come on the road in marsh and forest; its blood and its
core are worth having. A tempering draught and a day's bath raise the body.
"""

import systems.encounters as encounters
import systems.toxins as toxins
from systems import factions as F
from systems.bodies import load_body, save_body
from systems.facts import make_variant, place_name, record_fact
from systems.items import create_manual
from systems.purse import silver_of
from systems.realms import add_energy
from systems.techniques import create_technique, generate, known_arts
from world.body import PHYSIQUE, add_injury
from world.events import Event, effect
from world.seed import rng_for

POISON_BODY = "Myriad Poison Body"
PATH_MASTERY = 0.3
QI_PER_POINT = 0.02
TURNING = 60.0
IMMUNE_GRADE = 3
BLOOD_GRADE, BLOOD_STRENGTH = 3, 2
BARE_FORMS = frozenset({"bare", "claws", "palm", "fist", "finger"})
ART_PRICE = 300
BEAST_CHANCE, BEAST_TERRAINS = 0.03, frozenset({"marsh", "forest"})
BEASTS = ("great python", "red toad", "golden centipede")
BITE_GRADE, BITE_STRENGTH = 4, 8
BLOOD_RESIST, BLOOD_QI, CORE_QI, CORE_VENOM = 2, 1.0, 3.0, 10.0
BATH_PRICE, BATH_LIMIT, BATH_PAIN, AWAKEN = 30, 3, 0.3, 0.2
AWAKENING = {"fire": "Pure Yang Body", "water": "Nine Yin Body", "metal": "Heavenly Sword Bones",
             "earth": "Iron Bone Body", "wood": "Dragon Vein Body", "poison": POISON_BODY}


# --- the poison path ---------------------------------------------------------------------------------------

def poison_mastery(world, person: int) -> tuple[float, str | None]:
    """The best mastery of a poison art this person knows, and its form."""
    arts = [a for a in known_arts(world, person) if a.technique.data.get("element") == "poison"
            and a.technique.data.get("category") == "martial"]
    best = max(arts, key=lambda a: a.mastery, default=None)
    return (best.mastery, best.technique.data["form"]) if best else (0.0, None)


def conversion(world, person: int, body) -> float:
    mastery, _ = poison_mastery(world, person)
    if mastery < PATH_MASTERY:
        return 0.0
    return min(0.9, 0.3 + 0.5 * mastery + 0.05 * body.realm)


def _absorb(world, person: int, body, grade: int, strength: int) -> tuple[int, int]:
    """A practitioner takes a poison in: part becomes qi and venom, the rest is suffered (spec 4.3)."""
    share = conversion(world, person, body)
    if not share:
        return grade, strength
    points = share * grade * strength
    add_energy(body, points * QI_PER_POINT)
    body.venom = min(100.0, round(body.venom + points, 3))
    if body.venom >= TURNING and body.constitution != POISON_BODY:
        body.constitution, body.constitution_known = POISON_BODY, True
        here = world.targets(person, "located_in")
        poison_body_news(world, person, here[0] if here else None)
    return grade, int(strength * (1 - share))


def _immune(world, person: int, body, grade: int, strength: int) -> tuple[int, int]:
    """A Myriad Poison Body shrugs off the lesser poisons (spec 4.4)."""
    if body.constitution == POISON_BODY and grade <= IMMUNE_GRADE:
        return grade, 0
    return grade, strength


toxins.ABSORB_HOOKS.extend([_immune, _absorb])


def _strikes(world, hitter: int, target: int, form: str, hitter_body, target_body) -> None:
    """A poison art's wound leaves poison; a Poison Body's blood poisons a bare-handed striker; a venomous beast
    bites with venom (spec 4.3, 4.4, 4.6)."""
    mastery, art_form = poison_mastery(world, hitter)
    if mastery >= PATH_MASTERY and form == art_form:
        toxins.add_poison(world, target, target_body, 1 + int(mastery * 3), 2, "a poison art")
    if world.entity(hitter).data.get("venomous"):
        toxins.add_poison(world, target, target_body, BITE_GRADE, BITE_STRENGTH, "a venomous bite")
    if target_body.constitution == POISON_BODY and form in BARE_FORMS:
        toxins.add_poison(world, hitter, hitter_body, BLOOD_GRADE, BLOOD_STRENGTH, "a poison body's blood")


toxins.WOUND_HOOKS.append(_strikes)


def turned(world, person: int) -> bool:
    return load_body(world, person).constitution == POISON_BODY


def poison_body_news(world, person: int, place) -> None:
    """The world comes to hear of a Poison Body (spec 4.4): a fact like any other."""
    variant = make_variant("poison_body", person, None, place=place_name(world, place) if place else None)
    record_fact(world, person, "poison_body", None, place=place, weight=2.0, variant=variant)


# --- poison arts from an unorthodox clan's keeper -------------------------------------------------------------

def art_block(world, player: int, npc: int) -> str | None:
    from systems.scheming import buy_poison_block
    why = buy_poison_block(world, player, npc)
    if why is not None and why != "A poison costs 50 silver.":
        return "They teach no poisons."
    if silver_of(world, player) < ART_PRICE:
        return f"A poison art's manual costs {ART_PRICE} silver."
    return None


def art_events(world, player: int, npc: int, place) -> list[Event]:
    return [Event("poison_art_bought", (player, npc), place, {"silver": ART_PRICE})]


@effect("poison_art_bought")
def _art_bought(world, event) -> None:
    player, keeper = event.actors
    world.update_data(player, silver=silver_of(world, player) - ART_PRICE)
    world.update_data(keeper, silver=silver_of(world, keeper) + ART_PRICE)
    rng = rng_for(world.world_seed, f"poison_art:{player}:{world.time}")
    name, data = generate(rng, "martial", form=rng.choice(F.FAVOURED["unorthodox_clan"]), grade=2, element="poison")
    create_manual(world, player, create_technique(world, name, data), 1.0)


# --- venomous beasts -------------------------------------------------------------------------------------------

def venomous_beast(world, player: int, region) -> int | None:
    """When a beast comes on the roads of marsh and forest, it may be a great venomous one (spec 4.6); its own roll."""
    if region.data["terrain"] not in BEAST_TERRAINS:
        return None
    own = rng_for(world.world_seed, f"venomous:{player}:{world.time}")
    if own.random() >= BEAST_CHANCE:
        return None
    index = 0
    while world.entity_by_seed(f"{region.seed_path}/venomous:{index}") is not None:
        index += 1
    path = f"{region.seed_path}/venomous:{index}"
    species = own.choice(BEASTS)
    beast = world.add_entity("person", f"a {species}", {
        "beast": True, "venomous": True, "occupation": species, "traits": ["hot-tempered"], "realm": "second-rate",
        "roamer": True, "roamer_kind": "beast", "silver": 0}, path)
    world.relate(beast, region.id, "located_in")
    return beast


encounters.BEAST_HOOKS.append(venomous_beast)


def butcher_block(world, player: int, beast: int, place) -> str | None:
    data = world.entity(beast).data if world.entity(beast) is not None else {}
    if not data.get("venomous") or not data.get("dead") or data.get("butchered"):
        return "There is nothing to take."
    return None


def butcher_events(world, player: int, beast: int, place, part: str) -> list[Event]:
    return [Event("beast_butchered", (player, beast), place, {"part": part})]


@effect("beast_butchered")
def _butchered(world, event) -> None:
    player, beast = event.actors
    world.update_data(beast, butchered=True)
    body = load_body(world, player)
    if event.data["part"] == "blood":
        body.resist = max(body.resist, BLOOD_RESIST)
        add_energy(body, BLOOD_QI)
    else:
        add_energy(body, CORE_QI)
        if conversion(world, player, body):
            body.venom = min(100.0, body.venom + CORE_VENOM)
    save_body(world, player, body)


# --- tempering baths -------------------------------------------------------------------------------------------

def bath_block(world, person: int, place, stat: str, draught: int | None) -> str | None:
    if stat not in PHYSIQUE:
        return "No bath raises that."
    item = world.entity(draught) if draught is not None else None
    if item is None or item.kind != "pill" or item.data.get("effect") != "tempering" or draught not in world.targets(person, "owns"):
        return "A tempering bath needs a tempering draught."
    if load_body(world, person).baths.get(stat, 0) >= BATH_LIMIT:
        return f"Baths can raise your {stat} no further."
    if world.entity(place).kind != "town":
        return "A bath needs an inn or your sect's hall."
    if not _own_hall(world, person, place) and silver_of(world, person) < BATH_PRICE:
        return f"The inn's bath costs {BATH_PRICE} silver."
    return None


def _own_hall(world, person: int, place) -> bool:
    return any(world.entity(f).data.get("seat") == place and d.get("status", "member") == "member"
               for f, _, d in F.memberships(world, person))


def bath_events(world, person: int, place, stat: str, draught: int, herb: int | None = None) -> list[Event]:
    from systems.herbs import herb_info
    rng = rng_for(world.world_seed, f"bath:{person}:{world.time}")
    info = herb_info(world.entity(herb)) if herb is not None else None
    awaken = None
    if info is not None and info[1] >= 3 and rng.random() < AWAKEN:
        awaken = AWAKENING.get(_element(info[0]))
    return [Event("bathed", (person,), place, {
        "stat": stat, "draught": draught, "herb": herb, "pain": rng.random() < BATH_PAIN, "awaken": awaken,
        "price": 0 if _own_hall(world, person, place) else BATH_PRICE})]


def _element(name: str) -> str:
    from systems.herbs import props
    return props(name)["element"]


@effect("bathed")
def _bathed(world, event) -> None:
    person, d = event.actors[0], event.data
    world.update_data(person, silver=silver_of(world, person) - d["price"])
    for item in (d["draught"], d["herb"]):
        if item is not None:
            world.unrelate(person, "owns", item)
            world.update_data(item, used=True)
    body = load_body(world, person)
    body.physique[d["stat"]] = min(20, body.physique[d["stat"]] + 1)
    body.baths = {**body.baths, d["stat"]: body.baths.get(d["stat"], 0) + 1}
    if d["pain"]:
        add_injury(body, "torso", "internal", 1, world.time, "a tempering bath")
    if d["awaken"] and body.constitution is None:
        body.constitution, body.constitution_known = d["awaken"], True
    save_body(world, person, body)
    from systems.time import advance
    advance(world, 4)
