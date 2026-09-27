"""NPC alchemy (phase 5c spec 5.4): a lives agenda, one seeded roll per person per season, no entities made.

Alchemists (herbalists by trade and the sects' pill masters) refine 1-3 pills a season of grade ceil(rank / 2),
kept as a count on the person (`pills`: {grade: count}), and now and then rise a Guild rank. Anyone of realm 1 or
more with silver may take a pill in a season: half a year of cultivation, and residue that, past 60, risks a
deviation. The pills become things only when the player takes them: robbed or taken from the slain, bought at an
alchemist's stall, or inherited.
"""

import math

import systems.agendas  # noqa: F401  the life clock's own agendas come first, whatever is imported first
import systems.guild as G
import systems.lives as lives
import systems.pill_hall as PH
from systems.bodies import load_body
from systems.purse import silver_of
from systems.realms import realm_index
from world.body import add_injury, to_dict
from world.events import Event, effect, listen
from world.seed import rng_for

REFINE = (1, 3)
RISE_CHANCE = 0.1
TAKE_CHANCE = 0.3
PILL_YEARS = 0.5
RESIDUE_PER_GRADE = 3
DEVIATION_AT, DEVIATION_CHANCE, DEADLY = 60, 0.02, 0.1
BUY_PRICE = 20             # an NPC buys a pill for this x grade, when they have none of their own
STALL_PRICE = 30           # the player buys at an alchemist's stall for this x grade squared
MAX_HELD = 12


def held(entity) -> dict[int, int]:
    return {int(k): v for k, v in (entity.data.get("pills") or {}).items() if v > 0}


def season_events(world, person: int, n: int, rng) -> list[Event]:
    """This season's refining and pill-taking for one NPC, from its own seeded stream (not the life clock's)."""
    entity = world.entity(person)
    mine = rng_for(world.world_seed, f"npc_alchemy:{lives.key(entity)}:{n}")
    data: dict = {"season": n, "refined": 0, "grade": 0, "rank": None, "took": None, "deviation": False,
                  "dies": False, "bought": 0}
    occupation = entity.data.get("occupation")
    alchemist = occupation in G.ALCHEMIST_JOBS or (occupation == "hall keeper" and G.is_pill_master(world, person))
    if alchemist:
        rank = G.rank_of(world, person) or 1
        data["grade"] = min(5, max(1, math.ceil(rank / 2)))
        data["refined"] = mine.randint(*REFINE)
        if rank < G.MAX_RANK and mine.random() < RISE_CHANCE:
            data["rank"] = rank + 1
    if realm_index(entity.data.get("realm", "mortal")) >= 1 and mine.random() < TAKE_CHANCE:
        own = held(entity)
        if own or data["refined"]:
            data["took"] = max(own) if own else data["grade"]
        elif silver_of(world, person) >= BUY_PRICE:
            data["took"], data["bought"] = 1, BUY_PRICE
        if data["took"]:
            residue = float((entity.data.get("body") or {}).get("residue", 0.0))
            if residue >= DEVIATION_AT and mine.random() < DEVIATION_CHANCE:
                data["deviation"] = True
                data["dies"] = mine.random() < DEADLY
    if not data["refined"] and not data["took"] and data["rank"] is None:
        return []
    events = [Event("npc_alchemy", (person,), lives.home(world, person), data)]
    if data["dies"] and lives.home(world, person) is not None:
        events.append(Event("died", (person, person), lives.home(world, person), {"cause": "deviation", "world": True}))
    return events


lives.AGENDAS.append(season_events)


@effect("npc_alchemy")
def _season(world, event) -> None:
    person, d = event.actors[0], event.data
    entity = world.entity(person)
    pills = held(entity)
    changes: dict = {}
    if d["refined"]:
        pills[d["grade"]] = min(MAX_HELD, pills.get(d["grade"], 0) + d["refined"])
    if d["rank"] is not None:
        changes["guild_rank"] = d["rank"]
    if d["took"]:
        if pills.get(d["took"]):
            pills[d["took"]] -= 1
        if d["bought"]:
            changes["silver"] = silver_of(world, person) - d["bought"]
        body = dict(entity.data.get("body") or to_dict(load_body(world, person)))
        body["energy_years"], body["bottleneck"] = lives._grown(body, PILL_YEARS)
        body["residue"] = min(100.0, float(body.get("residue", 0.0)) + RESIDUE_PER_GRADE * d["took"])
        changes["body"] = body
    changes["pills"] = {str(k): v for k, v in pills.items() if v > 0}
    world.update_data(person, **changes)
    if d["deviation"] and not d["dies"]:
        body = load_body(world, person)
        add_injury(body, "torso", "internal", 3, world.time, "a qi deviation")
        from systems.bodies import save_body
        save_body(world, person, body)


# --- the pills made things ----------------------------------------------------------------------------------

def materialize(world, holder: int, taker: int, how: str, count: int | None = None) -> list[int]:
    """Some of an NPC's pills become pills the taker carries: the strongest first."""
    entity = world.entity(holder)
    pills = held(entity)
    made = []
    for grade in sorted(pills, reverse=True):
        while pills[grade] > 0 and (count is None or len(made) < count):
            pills[grade] -= 1
            rng = rng_for(world.world_seed, f"npc_pill:{holder}:{grade}:{pills[grade]}")
            made.append(PH.make_hall_pill(world, taker, holder, grade, rng.choice(PH.EFFECTS), how))
    world.update_data(holder, pills={str(k): v for k, v in pills.items() if v > 0})
    return made


@listen("duel_ended")
def _robbed(world, event, event_id: int) -> None:
    """What a robbed or slain NPC carried goes with their manuals to the victor (spec 5.4)."""
    player, opponent = event.actors
    if event.data.get("by") == "player" and event.data.get("verdict") in ("rob", "kill") \
            and held(world.entity(opponent)):
        materialize(world, opponent, player, "taken")


@listen("died")
def _inherited(world, event, event_id: int) -> None:
    dead = event.actors[-1]
    entity = world.entity(dead)
    if entity is None or not held(entity):
        return
    from systems.kin import kin_of
    heir = next((k for k, _ in kin_of(world, dead) if not world.entity(k).data.get("dead")), None)
    if heir is None:
        return
    if world.entity(heir).data.get("is_player"):
        materialize(world, dead, heir, "inherited")
        return
    pills = held(world.entity(heir))
    for grade, count in held(entity).items():
        pills[grade] = min(MAX_HELD, pills.get(grade, 0) + count)
    world.update_data(heir, pills={str(k): v for k, v in pills.items()})
    world.update_data(dead, pills={})


# --- an alchemist's stall -------------------------------------------------------------------------------------

def stall_price(grade: int) -> int:
    return STALL_PRICE * grade ** 2


def stall_offers(world, npc: int) -> list[int]:
    """The grades an alchemist has pills of to sell."""
    return sorted(held(world.entity(npc)), reverse=True) if G.is_alchemist(world, npc) else []


def stall_block(world, person: int, npc: int, grade: int) -> str | None:
    if grade not in stall_offers(world, npc):
        return "They have no such pills."
    if silver_of(world, person) < stall_price(grade):
        return f"They ask {stall_price(grade)} silver."
    return None


def stall_events(world, person: int, npc: int, grade: int, place) -> list[Event]:
    return [Event("npc_pill_bought", (person, npc), place, {"grade": grade, "price": stall_price(grade)})]


@effect("npc_pill_bought")
def _bought(world, event) -> None:
    person, npc = event.actors
    d = event.data
    world.update_data(person, silver=silver_of(world, person) - d["price"])
    world.update_data(npc, silver=silver_of(world, npc) + d["price"])
    pills = held(world.entity(npc))
    pills[d["grade"]] -= 1
    rng = rng_for(world.world_seed, f"npc_pill:{npc}:{d['grade']}:{pills[d['grade']]}")
    world.update_data(npc, pills={str(k): v for k, v in pills.items() if v > 0})
    PH.make_hall_pill(world, person, npc, d["grade"], rng.choice(PH.EFFECTS), "bought")
