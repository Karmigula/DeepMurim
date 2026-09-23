"""Founding a sect (phase 3c spec 4): sworn followers, the charter, the founding choices."""

import systems.land as land
from systems import factions as F
from systems.attitude import attitude
from systems.beliefs import apparent_to
from systems.facts import make_variant, place_name, record_fact
from systems.membership import open_martial
from systems.purse import payment_events, silver_of
from systems.realms import realm_index
from systems.reputation import EPITHET_RENOWN, reputation
from world.events import Event, Witness, effect, listen
from world.gen.names import person_name
from world.gen.npc import OCCUPATIONS, PORTRAIT_PARTS, TRAITS
from world.seed import rng_for

CHARTER = 200
FOLLOWERS_NEEDED = 3
MIN_REALM = 2
PRESETS = {"orthodox": F.LADDERS["orthodox_sect"], "clan": F.LADDERS["martial_clan"],
           "beggars": F.LADDERS["beggars"], "cult": F.LADDERS["demonic_cult"]}
TABOOS = ("never_kill_unarmed", "never_teach_outsiders", "never_spare_cultists", "never_rob", "never_desert_a_duel")
TRIALS = ("spar", "service", "ears", "escort", "blood")
TRIAL_TERMS = {"spar": "a sparring match", "service": "a season of service", "ears": "a season as your eyes and ears",
               "escort": "an escort on the roads", "blood": "an oath sworn in blood"}
PATH_TRAITS = {"righteous": {"kind", "honest"}, "ruthless": {"cunning", "hot-tempered"}}
RENOWN_BANDS = {"unknown": 0, "little known": 1, "known": 2, "renowned": 3, "famous": 4}
NAME_ENDS = ("Sect", "Hall", "Gate")


def my_sect(world, player: int) -> int | None:
    sect = world.entity(player).data.get("sect")
    return sect if sect and not world.entity(sect).data.get("dissolved") else None


def followers(world, player: int) -> list[int]:
    return [p.id for p in world.entities("person")
            if p.data.get("sworn_to") == player and not p.data.get("dead")]


def can_ask_to_follow(world, npc: int, player: int) -> bool:
    entity = world.entity(npc)
    if entity.data.get("is_player") or entity.data.get("beast") or entity.data.get("sworn_to") or F.memberships(world, npc):
        return False
    return attitude(world, npc, apparent_to(world, npc, player)).score >= 0.3


def follow_chance(world, npc: int, player: int, town: int) -> float:
    rep = reputation(world, town, apparent_to(world, town, player))
    traits = set(world.entity(npc).data.get("traits", ()))
    match = 1.0 if rep.path == "hard to read" or traits & PATH_TRAITS.get(rep.path, set()) else 0.0
    return max(0.0, min(1.0, 0.2 + 0.1 * RENOWN_BANDS.get(rep.word, 0) + 0.2 * match))


def sworn_events(world, player: int, npc: int, place: int) -> list[Event]:
    roll = rng_for(world.world_seed, f"sworn:{npc}:{player}:{world.time}").random()
    accepted = roll < follow_chance(world, npc, player, place)
    witness = Witness(npc, "grateful" if accepted else "annoyed", 0.3 if accepted else 0.2)
    return [Event("sworn", (player, npc), place, {"accepted": accepted}, witnesses=(witness,))]


@effect("sworn")
def _sworn(world, event) -> None:
    if event.data["accepted"]:
        world.update_data(event.actors[1], sworn_to=event.actors[0])


def found_block(world, player: int, town: int) -> str | None:
    me = world.entity(player)
    if land.owner_of(world, town) != player:
        return "You must own land here."
    if reputation(world, town, apparent_to(world, town, player)).renown < EPITHET_RENOWN:
        return "You must be renowned in this town."
    if realm_index(me.data.get("realm", "mortal")) < MIN_REALM:
        return "You must be at least Second-rate."
    if any(world.entity(f).data["type"] in F.MARTIAL and world.entity(f).data["type"] != "player_sect"
           for f, _, d in F.memberships(world, player) if d.get("status", "member") == "member"):
        return "You must leave your martial faction first."  # a secret membership counts too
    if len(followers(world, player)) < FOLLOWERS_NEEDED:
        return f"You need {FOLLOWERS_NEEDED} sworn followers."
    if silver_of(world, player) < CHARTER:
        return f"The charter costs {CHARTER} silver."
    if my_sect(world, player) is not None:
        return "You already lead a sect."
    return None


def name_suggestions(world, player: int) -> list[str]:
    rng = rng_for(world.world_seed, f"sect-names:{player}")
    names: list[str] = []
    while len(names) < 3:
        name = f"{rng.choice(F.SECT_A)} {rng.choice(F.SECT_B)} {rng.choice(NAME_ENDS)}"
        if name not in names:
            names.append(name)
    return names


def make_person(world, path: str, town: int, **overrides) -> int:
    """A seeded person standing in `town` (recruits, followers made on the spot)."""
    rng = rng_for(world.world_seed, path)
    surname, given = person_name(rng)
    data = {"surname": surname, "given": given, "gender": rng.choice(("man", "woman")), "age": rng.randint(16, 40),
            "occupation": rng.choice(OCCUPATIONS), "traits": rng.sample(TRAITS, 2), "realm": "mortal",
            "portrait": {part: rng.randrange(count) for part, count in PORTRAIT_PARTS.items()}}
    data.update(overrides)
    person = world.add_entity("person", f"{data['surname']} {data['given']}", data, path)
    world.relate(person, town, "located_in")
    return person


def founded_events(world, player: int, magistrate: int, town: int, choice: dict) -> list[Event]:
    return payment_events(player, magistrate, town, CHARTER, "charter") + [
        Event("sect_founded", (player, magistrate), town, dict(choice))]


def _talent(world, person: int) -> float:
    key = world.entity(person).seed_path or person  # the same recruit has the same talent in every playthrough
    return round(rng_for(world.world_seed, f"talent:{key}").uniform(0.5, 1.5), 2)


def enrol(world, person: int, sect: int, loyalty: int, role: str = "disciple", rank: int = 0) -> None:
    """Make someone a member of the player's sect, standing at its seat."""
    seat = world.entity(sect).data["seat"]
    world.relate(person, sect, "member_of", rank, {"role": role, "hall": None, "merit": 0, "status": "member",
                                                  "secret": False})
    world.update_data(person, loyalty=loyalty, talent=_talent(world, person), on_duty=False,
                      sect_joined_at=world.time, sworn_to=None)
    world.unrelate(person, "located_in")
    world.relate(person, seat, "located_in")


@effect("sect_founded")
def _founded(world, event) -> None:
    player, town, choice = event.actors[0], event.place, event.data
    here = world.entity(town).data
    data = {"type": "player_sect", "tier": "minor", "home": [here["x"], here["y"]], "seat": town,
            "path": choice["path"], "taboos": list(choice["taboos"]), "trial": choice["trial"],
            "ranks": list(PRESETS[choice["ranks"]]), "treasury": 0, "power": 20, "wealth": 0, "buildings": {},
            "last_tick": world.time, "founder": player, "dissolved": False, "chronicle": [], "arts": [],
            "forms": [], "branches": []}
    sect = world.add_entity("faction", choice["name"], data, f"sect:{player}:{world.time}")
    world.relate(player, sect, "member_of", 4, {"role": "leader", "hall": None, "merit": 0, "status": "member",
                                               "secret": False, "joined_at": world.time, "judged": []})
    for person in followers(world, player):
        enrol(world, person, sect, 60)
    world.update_data(town, halls=[*here.get("halls", []), sect], seats=[*here.get("seats", []), sect])
    world.update_data(player, sect=sect)
    model = {"righteous": "orthodox_sect", "ruthless": "demonic_cult"}.get(choice["path"])
    for other in F.ensure_roster(world):
        value = F.base_stance(model, world.entity(other).data["type"]) if model else 0.0
        if value:
            world.relate(sect, other, "stance", value)
            world.relate(other, sect, "stance", value)


@listen("sect_founded")
def _founded_fact(world, event, event_id: int) -> None:
    player = event.actors[0]
    sect = world.entity(player).data["sect"]
    record_fact(world, player, "founded", sect, place=event.place, source_event=event_id, weight=3.0,
                variant=make_variant("founded", player, sect, place=place_name(world, event.place)))
