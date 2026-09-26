"""What the fallen carried (phase 5a spec 4.2): the victor may take their weapon and armour.

Taking from someone lawful is robbery as the law sees it (a `robbed` fact); from a bandit, a demonic cult's
member, or one with a price on their head, it is not. The living loser never forgets it. An NPC who beats the
player may take the player's weapon: the greedy and the ruthless do, half the time.
"""

import systems.gear as gear
from systems import factions as F
from systems.attitude import is_bandit
from systems.duel import covets
from systems.facts import make_variant, place_name, record_fact
from world.events import Event, Witness, commit, listen
from world.seed import rng_for

THEFT_WEIGHT = 1.5
NPC_TAKES = 0.5
PROUD = frozenset({"proud", "hot-tempered"})


def beaten_by(world, winner: int, loser: int) -> bool:
    """The loser lies dead, or lost their last fight with the winner."""
    if world.entity(loser).data.get("dead"):
        return True
    for entry in world.chronicle_about(winner, limit=40):
        if entry.kind == "duel_ended" and loser in entry.actors:
            return entry.data.get("result") == "won" and entry.data.get("by") == "player"
    return False


def lawful(world, person: int, place: int | None = None) -> bool:
    """Not a bandit, not of a demonic cult, and with no price on their head in this town."""
    if is_bandit(world.entity(person)):
        return False
    if place is not None and world.entity(place).kind == "town":
        from systems.law import bounty  # the law comes after the duel in the import graph
        if bounty(world, place, person) > 0:
            return False
    return not any(world.entity(f).data.get("type") == "demonic_cult" and d.get("status", "member") == "member"
                   for f, _, d in F.memberships(world, person))


def take_block(world, taker: int, loser: int, slot: str, place: int) -> str | None:
    if place not in world.targets(loser, "located_in"):
        return "They are not here."
    if not beaten_by(world, taker, loser):
        return "You have not beaten them."
    carried = gear.weapon_of(world, loser) if slot == "weapon" else gear.armour_of(world, loser)
    if carried is None:
        return "They carry nothing of the kind."
    if slot == "weapon" and carried["item"] is None and gear.best_weapon_form(world, loser) is None \
            and not gear.carried(world, loser).get("form"):
        return "They fought with their hands."
    return None


def take_events(world, taker: int, loser: int, slot: str, place: int) -> list[Event]:
    item = gear.materialize(world, loser, slot)
    living = not world.entity(loser).data.get("dead")
    feelings = ()
    if living:
        proud = PROUD & set(world.entity(loser).data.get("traits", ()))
        feelings = (Witness(loser, "hatred" if proud else "wronged", 0.8, True),)
    return gear.pass_events(world, loser, taker, item, place, "taken") + [
        Event("gear_seized", (taker, loser), place, {"item": item, "lawful": lawful(world, loser, place), "living": living},
              witnesses=feelings)]


@listen("gear_seized")
def _seized(world, event, event_id: int) -> None:
    if not event.data["lawful"]:
        return
    taker, loser = event.actors
    variant = make_variant("robbed", taker, loser, place=place_name(world, event.place))
    record_fact(world, taker, "robbed", loser, place=event.place, source_event=event_id, weight=THEFT_WEIGHT,
                variant=variant)


@listen("duel_ended")
def _victor_takes(world, event, event_id: int) -> None:
    """An NPC who beats the player may take the player's weapon (spec 4.2)."""
    d = event.data
    player, opponent = event.actors
    if d.get("by") != "opponent" or d.get("verdict") in ("kill", "spare") or d.get("mode") in ("spar", "test", "bout"):
        return
    victor = world.entity(opponent)
    ruthless = {"cunning", "greedy"} <= set(victor.data.get("traits", ()))
    if not (covets(victor) or ruthless) or gear.weapon_of(world, player) is None:
        return
    if rng_for(world.world_seed, f"spoils:{event_id}").random() >= NPC_TAKES:
        return
    item = gear.materialize(world, player, "weapon")
    if item is not None:
        commit(world, gear.pass_events(world, player, opponent, item, event.place, "taken"))
