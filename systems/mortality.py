"""Mortality (phase 4b spec 3): the player ages with the world and can die of age, deviation, a blade or the law.

The player's death is the ordinary `died` event, flagged `player: True`, so every
death rule of 3a-4a applies to them too; a listener here opens the death screen.
"""

import systems.lives as lives
from systems.bodies import load_body
from systems.facts import make_variant, place_name, record_fact
from world.events import Event, effect, listen
from world.seed import rng_for

DEVIATION_DEATH = 0.5
WHITE_HAIR = 10          # years before the lifespan when the warning comes
DEATH_WEIGHT = 3.0
CAUSES = {"age": "of old age", "illness": "of illness", "deviation": "of qi deviation",
          "killed": "at the hands of {killer}", "executed": "under the executioner's blade"}


def player_lived_to(world, player: int) -> int:
    """The last season the player has lived; an old save's player starts living now (spec §9)."""
    found = world.entity(player).data.get("lived_to")
    if found is None:
        found = lives.current_season(world)
        world.update_data(player, lived_to=found)
    return found


def lifespan(world, player: int) -> int:
    return lives.LIFESPAN[load_body(world, player).realm]


def lifespan_near(world, player: int) -> bool:
    return float(world.entity(player).data.get("age", 18)) >= lifespan(world, player) - WHITE_HAIR


def death_events(world, player: int, cause: str, killer: int | None, age: float | None = None) -> list[Event]:
    place = lives.home(world, player)
    age = float(world.entity(player).data.get("age", 18)) if age is None else age
    return [Event("died", (killer or player, player), place, {"cause": cause, "player": True, "age": age})]


def age_events(world, player: int) -> list[Event]:
    """The player lives the seasons the world has passed; the last may be their death."""
    entity = world.entity(player)
    if entity.data.get("dead") or entity.data.get("dying"):
        return []
    done, now = player_lived_to(world, player), lives.current_season(world)
    if done >= now:
        return []
    realm = load_body(world, player).realm
    life = lives.LIFESPAN[realm]
    age = float(entity.data.get("age", 18))
    warned = bool(entity.data.get("white_hair"))
    white, died = False, None
    for n in range(done + 1, now + 1):
        age = round(age + 0.25, 2)
        if not warned and age >= life - WHITE_HAIR:
            warned = white = True
        if rng_for(world.world_seed, f"life:player:{player}:{n}").random() < lives.death_chance(age, realm):
            died = n
            break
    events = [Event("player_aged", (player,), lives.home(world, player),
                    {"season": died or now, "age": age, "white_hair": white})]
    if died is not None:
        events += death_events(world, player, "age", None, age)
    return events


def deviation_death_events(world, player: int, event_id: int) -> list[Event]:
    if rng_for(world.world_seed, f"deviation-death:{player}:{event_id}").random() < DEVIATION_DEATH:
        return death_events(world, player, "deviation", None)
    return []


def epitaph(world, player: int) -> str:
    entity = world.entity(player)
    d = entity.data.get("dying") or {}
    killer = world.entity(d["killer"]).name if d.get("killer") else "someone"
    how = CAUSES.get(d.get("cause"), "").format(killer=killer)
    where = place_name(world, d.get("place")) or "the road"
    age = int(d.get("age") or entity.data.get("age", 18))
    return f"{entity.name} died {how} in {where}, aged {age}."


@effect("player_aged")
def _aged(world, event) -> None:
    d = event.data
    changes = {"age": d["age"], "lived_to": d["season"]}
    if d["white_hair"]:
        changes["white_hair"] = True
    world.update_data(event.actors[0], **changes)


@listen("died")
def _player_died(world, event, event_id: int) -> None:
    """The player's death opens the death screen and becomes the talk of the town."""
    if not event.data.get("player"):
        return
    killer, victim = event.actors
    world.update_data(victim, dying={"cause": event.data["cause"], "killer": killer if killer != victim else None,
                                     "place": event.place, "time": world.time, "age": event.data.get("age")})
    where = place_name(world, event.place)
    if killer == victim:
        record_fact(world, victim, "died", None, place=event.place, source_event=event_id, weight=DEATH_WEIGHT,
                    variant=make_variant("died", victim, None, place=where))
    else:
        record_fact(world, killer, "killed", victim, place=event.place, source_event=event_id, weight=DEATH_WEIGHT,
                    variant=make_variant("killed", killer, victim, place=where,
                                         realm=world.entity(killer).data.get("realm")))
