"""Bonds that make heirs (phase 4b spec 4): marriage, disciples, sworn siblings, and a named heir."""

import systems.agendas as agendas
import systems.lives as lives
import systems.sect as sect_mod
from systems.attitude import attitude
from systems.beliefs import apparent_to
from systems.facts import make_variant, place_name, record_fact
from systems.founding import followers, my_sect
from systems.kin import INVERSE, kin_of
from world.events import Event, effect, listen
from world.seed import rng_for

MARRY_ATTITUDE, DISCIPLE_ATTITUDE, SWORN_ATTITUDE = 0.5, 0.3, 0.7
HEIR_AGE = 14
INVERSE.setdefault("sworn_sibling", "sworn_sibling")


def warmth(world, npc: int, player: int) -> float:
    return attitude(world, npc, apparent_to(world, npc, player)).score


def accept_chance(score: float) -> float:
    return max(0.0, min(1.0, score))


def _age(entity) -> float:
    return float(entity.data.get("age", 30))


def _kin(world, person: int, role: str) -> list[int]:
    return [k for k, r in kin_of(world, person) if r == role]


def propose_block(world, player: int, npc: int) -> str | None:
    entity = world.entity(npc)
    if not 18 <= _age(entity) <= 50:
        return "They are not of an age to marry."
    if agendas.spouse_of(world, player) is not None:
        return "You are already married."
    if agendas.spouse_of(world, npc) is not None:
        return "They are already married."
    if npc in {k for k, _ in kin_of(world, player)}:
        return "They are family."
    refused = world.entity(player).data.get("spouse_refused", {})
    if refused.get(str(npc)) == lives.current_season(world):
        return "They gave you their answer this season."
    if warmth(world, npc, player) < MARRY_ATTITUDE:
        return "They do not feel that way about you."
    return None


def disciple_block(world, player: int, npc: int) -> str | None:
    entity = world.entity(npc)
    if not 12 <= _age(entity) <= 30:
        return "They are not of an age to be taught."
    if _kin(world, npc, "master"):
        return "They already have a master."
    if warmth(world, npc, player) < DISCIPLE_ATTITUDE:
        return "They would not follow your teaching."
    return None


def sworn_block(world, player: int, npc: int) -> str | None:
    if _age(world.entity(npc)) < 18:
        return "They are too young to swear an oath."
    if npc in _kin(world, player, "sworn_sibling"):
        return "You are already sworn."
    if warmth(world, npc, player) < SWORN_ATTITUDE:
        return "You are not close enough to swear an oath."
    return None


def propose_events(world, player: int, npc: int, place: int) -> list[Event]:
    n = lives.current_season(world)
    roll = rng_for(world.world_seed, f"propose:{player}:{npc}:{n}").random()
    accepted = roll < accept_chance(warmth(world, npc, player))
    return [Event("proposal", (player, npc), place, {"accepted": accepted, "season": n})]


def disciple_events(world, player: int, npc: int, place: int) -> list[Event]:
    return [Event("took_disciple", (player, npc), place, {})]


def sworn_events(world, player: int, npc: int, place: int) -> list[Event]:
    return [Event("sworn_siblings", (player, npc), place, {})]


def name_heir_events(world, player: int, npc: int, place: int) -> list[Event]:
    return [Event("named_heir", (player, npc), place, {})]


def candidates(world, player: int) -> list[tuple[int, str]]:
    """Who could carry on, in order (spec §4.2): named heir, children eldest first, disciples, sworn siblings, followers."""
    out: list[tuple[int, str]] = []
    seen: set[int] = set()

    def add(person, kind: str) -> None:
        entity = world.entity(person) if isinstance(person, int) else None
        if entity is None or person in seen or entity.kind != "person" or entity.data.get("dead") \
                or entity.data.get("is_player") or _age(entity) < HEIR_AGE:
            return
        seen.add(person)
        out.append((person, kind))

    add(world.entity(player).data.get("named_heir"), "named")
    for child in sorted(agendas.children_of(world, player), key=lambda p: (-_age(world.entity(p)), p)):
        add(child, "child")
    for pupil in _kin(world, player, "disciple"):
        add(pupil, "disciple")
    sect = my_sect(world, player)
    if sect is not None:
        members = sect_mod.members(world, sect)
        for person in sorted(members, key=lambda p: (-world.entity(p).data.get("loyalty", 0), -_age(world.entity(p)), p)):
            add(person, "disciple")
    for sibling in _kin(world, player, "sworn_sibling"):
        add(sibling, "sibling")
    for follower in followers(world, player):
        add(follower, "follower")
    return out


def is_candidate(world, player: int, person) -> bool:
    """Whether this person could inherit, without listing everyone who could."""
    entity = world.entity(person) if isinstance(person, int) else None
    if entity is None or entity.kind != "person" or entity.data.get("dead") or entity.data.get("is_player") \
            or _age(entity) < HEIR_AGE:
        return False
    if world.entity(player).data.get("named_heir") == person or entity.data.get("sworn_to") == player:
        return True
    if any(k == person and role in ("child", "disciple", "sworn_sibling") for k, role in kin_of(world, player)):
        return True
    sect = my_sect(world, player)
    return sect is not None and person in sect_mod.members(world, sect)


def relation_word(world, person: int, kind: str) -> str:
    woman = world.entity(person).data.get("gender") == "woman"
    return {"named": "your named heir", "child": "your daughter" if woman else "your son",
            "disciple": "your disciple", "sibling": "your sworn sister" if woman else "your sworn brother",
            "follower": "your sworn follower"}[kind]


@effect("proposal")
def _proposal(world, event) -> None:
    player, npc = event.actors
    if event.data["accepted"]:
        agendas._pair(world, player, npc, "spouse")
    else:
        refused = dict(world.entity(player).data.get("spouse_refused", {}))
        refused[str(npc)] = event.data["season"]
        world.update_data(player, spouse_refused=refused)


@effect("took_disciple")
def _took(world, event) -> None:
    agendas._pair(world, event.actors[0], event.actors[1], "disciple")


@effect("sworn_siblings")
def _sworn(world, event) -> None:
    agendas._pair(world, event.actors[0], event.actors[1], "sworn_sibling")


@effect("named_heir")
def _named(world, event) -> None:
    world.update_data(event.actors[0], named_heir=event.actors[1])


def _news(world, event, event_id: int, predicate: str) -> None:
    a, b = event.actors
    record_fact(world, a, predicate, b, place=event.place, source_event=event_id, weight=1.0,
                variant=make_variant(predicate, a, b, place=place_name(world, event.place)))


@listen("proposal")
def _proposal_news(world, event, event_id: int) -> None:
    if event.data["accepted"]:
        _news(world, event, event_id, "married")


@listen("took_disciple")
def _took_news(world, event, event_id: int) -> None:
    _news(world, event, event_id, "apprenticed")


@listen("sworn_siblings")
def _sworn_news(world, event, event_id: int) -> None:
    _news(world, event, event_id, "sworn_siblings")
