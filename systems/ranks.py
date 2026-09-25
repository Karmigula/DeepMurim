"""Rising in a faction (phase 3b spec 4, 5): promotion, stipends, sect arts, the library, gifts."""

from systems import factions as F
from systems.attitude import attitude
from systems.beliefs import apparent_to
from systems.facts import apparent, make_variant, place_name, record_fact
from systems.items import create_manual, manuals_of
from systems.membership import set_membership
from systems.purse import payment_events
from systems.realms import REALMS, realm_index
from systems.techniques import create_technique, generate, known_arts, teach
from world.events import Event, Witness, effect, listen
from world.seed import rng_for

MERIT_NEEDED = (30, 90, 250)
REALM_NEEDED = (0, 1, 2)
TOP_RANK = 3
STIPEND_DAYS, STIPEND_PER_RANK = 30, 10
WATCHES_PER_DAY = 4


def promotion_block(world, player: int, faction: int) -> str | None:
    """What stands between the player and the next rank, or None."""
    rank, data = F.membership(world, player, faction)
    if rank >= TOP_RANK:
        return "Only a crisis opens the leader's seat."  # phase 4g: claim it when it falls empty
    if data.get("merit", 0) < MERIT_NEEDED[rank]:
        return f"You need {MERIT_NEEDED[rank]} merit; you have {data.get('merit', 0)}."
    if realm_index(world.entity(player).data.get("realm", "mortal")) < REALM_NEEDED[rank]:
        return f"You must reach {REALMS[REALM_NEEDED[rank]].name} first."
    sponsor = data.get("sponsor")
    if rank == 2 and sponsor and attitude(world, sponsor, apparent_to(world, sponsor, player)).score < 0.3:
        return "Your sponsor does not favour you enough."
    return None


def promoted_events(world, player: int, faction: int, elder: int, place: int) -> list[Event]:
    rank = F.membership(world, player, faction)[0] + 1
    return [Event("promoted", (player, elder), place, {"faction": faction, "rank": rank})]


@effect("promoted")
def _promoted(world, event) -> None:
    set_membership(world, event.actors[0], event.data["faction"], rank=event.data["rank"], stipend_at=world.time)


@listen("promoted")
def _promoted_fact(world, event, event_id: int) -> None:
    me = apparent(event, event.actors[0])
    record_fact(world, me, "promoted", event.data["faction"], place=event.place, source_event=event_id, weight=0.5,
                variant=make_variant("promoted", me, event.data["faction"], place=place_name(world, event.place),
                                     masked=me != event.actors[0]))


def stipend_due(world, player: int, faction: int) -> int:
    rank, data = F.membership(world, player, faction)
    if rank < 1 or world.time - data.get("stipend_at", 0) < STIPEND_DAYS * WATCHES_PER_DAY:
        return 0
    return STIPEND_PER_RANK * rank


def stipend_events(world, player: int, faction: int, keeper: int, place: int) -> list[Event]:
    return [Event("stipend", (player, keeper), place, {"faction": faction, "amount": stipend_due(world, player, faction)})]


@effect("stipend")
def _stipend(world, event) -> None:
    player, faction = event.actors[0], event.data["faction"]
    world.update_data(player, silver=int(world.entity(player).data.get("silver", 0)) + event.data["amount"])
    set_membership(world, player, faction, stipend_at=world.time)


def sect_arts(world, faction: int) -> list[int]:
    """The faction's signature arts (3 for great, 2 for minor), made on first need."""
    entity = world.entity(faction)
    if entity.data.get("arts"):
        return list(entity.data["arts"])
    rng = rng_for(world.world_seed, f"{entity.seed_path}/arts")
    count = 3 if entity.data["tier"] == "great" else 2
    forms = entity.data["forms"]
    arts = []
    with world.transaction():
        for i in range(count):
            name, art = generate(rng, "martial", form=forms[i % len(forms)], grade=2 + i)
            arts.append(create_technique(world, name, art))
        world.update_data(faction, arts=arts)
    return arts


def teachable(world, player: int, faction: int) -> list[int]:
    rank = F.membership(world, player, faction)[0]
    known = {a.technique.id for a in known_arts(world, player)}
    arts = sect_arts(world, faction)
    return [a for i, a in enumerate(arts) if i <= rank and a not in known][:1]


def taught_events(world, player: int, elder: int, faction: int, place: int, technique: int) -> list[Event]:
    return [Event("sect_taught", (player, elder), place,
                  {"faction": faction, "technique": technique, "name": world.entity(technique).name})]


@effect("sect_taught")
def _taught(world, event) -> None:
    teach(world, event.actors[0], event.data["technique"], source="sect", teacher=event.actors[1])


def library_manual(world, player: int, faction: int) -> int | None:
    """A sect art the player may borrow as a manual: inner rank and up, not yet held or known."""
    rank = F.membership(world, player, faction)[0]
    if rank < 1:
        return None
    held = {m.technique.id for m in manuals_of(world, player)} | {a.technique.id for a in known_arts(world, player)}
    return next((a for i, a in enumerate(sect_arts(world, faction)) if i <= rank and a not in held), None)


def library_events(world, player: int, faction: int, place: int, technique: int) -> list[Event]:
    return [Event("library_lent", (player,), place,
                  {"faction": faction, "technique": technique, "name": world.entity(technique).name})]


@effect("library_lent")
def _lent(world, event) -> None:
    create_manual(world, event.actors[0], event.data["technique"], 1.0)


def gift_price(world, player: int, faction: int) -> int:
    return 20 * (F.membership(world, player, faction)[0] + 1)


def gift_events(world, player: int, elder: int, faction: int, place: int) -> list[Event]:
    amount = gift_price(world, player, faction)
    return payment_events(player, elder, place, amount, "gift") + [
        Event("gift", (player, elder), place, {"faction": faction, "amount": amount},
              witnesses=(Witness(elder, "grateful", 0.4),))]
