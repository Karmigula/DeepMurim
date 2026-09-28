"""The world's hearts (phase 5e spec 7): masters driven mad by their demons, and the enlightened.

A lives agenda: a master of Second-rate or more whose heart is troubled goes mad, one season in a hundred (one
hash; the heart is read only when the hash falls). A mad master calls the player out in town as an avenger does,
fights harder and never spares; after a year they come back to themselves, or it kills them. A master enlightened
in a dao resonance (4d) opens the dao of their art.
"""

import systems.craft_world  # noqa: F401  5d's agendas run before this one, whatever is imported first
import systems.daos as DA
import systems.encounters as encounters
import systems.heart as HT
import systems.lives as lives
from systems.facts import make_variant, place_name, record_fact
from systems.realms import realm_index
from world.events import Event, effect, listen
from world.gen.materialize import people_at
from world.seed import seed_for

MAD_REALM = 2              # Second-rate
MAD_CHANCE = 0.01          # a season
MAD_STEADY = 30.0          # only a heart under this goes mad
MAD_YEARS = 1
RECOVERY = 0.6
MAD_FIGHT = 1.2
ENLIGHTENED_DAO = 0.2


def mad(world, person: int) -> bool:
    entity = world.entity(person)
    return entity is not None and not entity.data.get("dead") and (entity.data.get("mad_until") or 0) > world.time


def season_events(world, person: int, n: int, rng) -> list[Event]:
    entity = world.entity(person)
    if entity.data.get("mad_until"):
        if entity.data["mad_until"] > world.time:
            return []
        place = lives.home(world, person)
        if seed_for(world.world_seed, f"mad_end:{lives.key(entity)}") / 2 ** 64 < RECOVERY:
            return [Event("madness_passed", (person,), place, {})]
        return [Event("died", (person, person), place, {"cause": "madness", "world": True})]
    if realm_index(entity.data.get("realm", "mortal")) < MAD_REALM:
        return []
    if seed_for(world.world_seed, f"madness:{lives.key(entity)}:{n}") / 2 ** 64 >= MAD_CHANCE:
        return []
    if HT.steady(world, person) >= MAD_STEADY:
        return []
    return [Event("heart_madness", (person,), lives.home(world, person),
                  {"until": world.time + MAD_YEARS * 4 * lives.SEASON, "season": n})]


lives.AGENDAS.append(season_events)


@effect("heart_madness")
def _maddened(world, event) -> None:
    world.update_data(event.actors[0], mad_until=event.data["until"])


@effect("madness_passed")
def _recovered(world, event) -> None:
    world.update_data(event.actors[0], mad_until=None)


@listen("heart_madness")
def _news(world, event, event_id: int) -> None:
    person = event.actors[0]
    variant = make_variant("went_mad", person, None, place=place_name(world, event.place),
                           realm=world.entity(person).data.get("realm", "mortal"))
    record_fact(world, person, "went_mad", None, place=event.place, source_event=event_id, weight=1.5,
                variant=variant)


def hunting(world, player: int) -> list[int]:
    """The mad in the player's town call them out, as avengers do."""
    here = next(iter(world.targets(player, "located_in")), None)
    return [p.id for p in people_at(world, here, exclude=player) if mad(world, p.id)] if here is not None else []


encounters.HUNTER_HOOKS.append(hunting)


def fight_factor(world, person: int) -> float:
    return MAD_FIGHT if mad(world, person) else 1.0


def enlighten(world, master: int) -> None:
    """A master enlightened (4d's dao resonance) opens the dao of their first art's form."""
    from systems.duel import ensure_npc_arts  # arts come after the heart in the import graph
    from systems.techniques import martial_arts
    ensure_npc_arts(world, master)
    arts = martial_arts(world, master)
    if arts:
        form = arts[0].technique.data["form"]
        daos = DA.daos(world, master)
        HT.write(world, master, daos={**daos, form: round(min(1.0, daos.get(form, 0.0) + ENLIGHTENED_DAO), 3)})


@listen("died")
def _mad_no_more(world, event, event_id: int) -> None:
    if world.entity(event.actors[-1]).data.get("mad_until"):
        world.update_data(event.actors[-1], mad_until=None)
