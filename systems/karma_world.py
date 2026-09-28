"""The world's karma (phase 5f spec 6): heaven strikes the wicked now and then, a heavy sinner's luck turns, and
temples take alms.

Retribution is a lives agenda of one hash (the karma is read only when it falls). The player's misfortune is a
season hook. A town with a monk has a temple.
"""

import systems.heart_world  # noqa: F401  5e's agenda runs before this one, whatever is imported first
import systems.karma as K
import systems.lives as lives
import systems.world_clock as world_clock
from systems.bodies import load_body, save_body
from systems.facts import make_variant, place_name, record_fact
from systems.purse import silver_of
from world.body import add_injury
from world.events import Event, effect, listen
from world.gen.materialize import people_at
from world.seed import rng_for, seed_for

STRUCK_CHANCE, STRUCK_BALANCE = 0.01, -50.0
MISFORTUNE_CHANCE, MISFORTUNE_BALANCE, PURSE_SHARE = 0.1, -150.0, 0.2
ALMS_MIN, ALMS_PER_MERIT, ALMS_CAP = 10, 10, 30   # merit = silver / 10, at most 30 a season


def season_events(world, person: int, n: int, rng) -> list[Event]:
    """The wicked struck down by heaven, one season in a hundred."""
    entity = world.entity(person)
    if seed_for(world.world_seed, f"struck:{lives.key(entity)}:{n}") / 2 ** 64 >= STRUCK_CHANCE:
        return []
    if K.balance(world, person) >= STRUCK_BALANCE:
        return []
    return [Event("died", (person, person), lives.home(world, person), {"cause": "heaven", "world": True})]


lives.AGENDAS.append(season_events)


@listen("died")
def _struck_news(world, event, event_id: int) -> None:
    if event.data.get("cause") != "heaven":
        return
    person = event.actors[-1]
    variant = make_variant("struck_down", person, None, place=place_name(world, event.place))
    record_fact(world, person, "struck_down", None, place=event.place, source_event=event_id, weight=1.5,
                variant=variant)


# --- the player's luck ------------------------------------------------------------------------------------------------

def season_hook(world, n: int) -> list[Event]:
    player = world.get_meta("player_id")
    entity = world.entity(player) if player is not None else None
    if entity is None or entity.data.get("dead") or K.balance(world, player) >= MISFORTUNE_BALANCE:
        return []
    rng = rng_for(world.world_seed, f"misfortune:{player}:{n}")
    if rng.random() >= MISFORTUNE_CHANCE:
        return []
    here = next(iter(world.targets(player, "located_in")), None)
    silver = silver_of(world, player)
    if silver and rng.random() < 0.5:
        return [Event("misfortune", (player,), here, {"what": "purse", "silver": int(silver * PURSE_SHARE)})]
    return [Event("misfortune", (player,), here, {"what": "injury", "silver": 0})]


world_clock.SEASON_HOOKS.append(season_hook)


@effect("misfortune")
def _misfortune(world, event) -> None:
    person, d = event.actors[0], event.data
    if d["what"] == "purse":
        world.update_data(person, silver=max(0, silver_of(world, person) - d["silver"]))
    else:
        body = load_body(world, person)
        add_injury(body, "left leg", "fracture", 2, world.time, "a fall no one saw coming")
        save_body(world, person, body)


# --- temples -----------------------------------------------------------------------------------------------------

def has_temple(world, town) -> bool:
    return world.entity(town).kind == "town" and any(p.data.get("occupation") == "monk" for p in people_at(world, town))


def alms_block(world, person: int, town, silver: int) -> str | None:
    if not has_temple(world, town):
        return "There is no temple here."
    if silver < ALMS_MIN or silver_of(world, person) < silver:
        return f"Alms are {ALMS_MIN} silver or more, from what you carry."
    return None


def alms_events(world, person: int, town, silver: int) -> list[Event]:
    season = lives.current_season(world)
    given = (world.entity(person).data.get("alms_merit") or {}).get(str(season), 0)
    merit = max(0, min(ALMS_CAP - given, silver // ALMS_PER_MERIT))
    return [Event("alms_given", (person,), town, {"silver": silver, "merit": merit, "season": season})]


@effect("alms_given")
def _alms(world, event) -> None:
    person, d = event.actors[0], event.data
    world.update_data(person, silver=silver_of(world, person) - d["silver"],
                      alms_merit={str(d["season"]): (world.entity(person).data.get("alms_merit") or {})
                                  .get(str(d["season"]), 0) + d["merit"]})
    K.add(world, person, merit=d["merit"])


def incense_events(world, person: int, town) -> list[Event]:
    return [Event("incense_burned", (person,), town, {})]


@effect("fortune_read")
def _fortune_paid(world, event) -> None:
    person, teller = event.actors
    world.update_data(person, silver=silver_of(world, person) - event.data["silver"])
    world.update_data(teller, silver=silver_of(world, teller) + event.data["silver"])
