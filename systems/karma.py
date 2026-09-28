"""Karma (phase 5f spec 2): heaven's own ledger of merit and sin, kept apart from the heart's view of itself.

A person's karma is person data `karma = {merit, sin, threads}` (threads: systems/threads.py). NPCs have none until
something writes it; until then it is read from their seed, occupation and traits. Deeds count (a table,
`systems/data/karma_deeds.toml`, a duel's verdict, and killing). Karma is never shown as a number: a fortune teller
reads it in words.
"""

import tomllib
from pathlib import Path

import systems.lives as lives
from world.events import listen
from world.seed import rng_for

DEEDS = tomllib.loads((Path(__file__).parent / "data" / "karma_deeds.toml").read_text(encoding="utf-8"))
VERDICTS = {"spare": ("merit", 5), "rob": ("sin", 5), "cripple": ("sin", 15)}
KILL_SIN, KILL_INNOCENT_SIN, KILL_WICKED_MERIT = 10, 40, 15
WICKED = -50               # a balance under this: killing them is merit
SINFUL = {"bandit"}, {"cunning", "greedy"}
VIRTUOUS = {"monk", "herbalist", "physician"}, {"kind", "honest"}
BALANCE_WORDS = ((100, "heaven smiles on you"), (30, "your merit outweighs your sins"),
                 (-30, "your merit and your sins stand even"), (-100, "your sins outweigh your merit"),
                 (-1e9, "heaven's patience with you is thin"))


def seeded(world, person: int) -> dict:
    """An NPC's karma before anything writes it: from their seed, trade and traits (spec 2)."""
    entity = world.entity(person)
    rng = rng_for(world.world_seed, f"karma:{lives.key(entity)}")
    occupation, traits = entity.data.get("occupation"), set(entity.data.get("traits") or [])
    sinful = occupation in SINFUL[0] or bool(traits & SINFUL[1])
    virtuous = occupation in VIRTUOUS[0] or bool(traits & VIRTUOUS[1])
    merit = rng.uniform(20, 80) if virtuous else rng.uniform(0, 30)
    sin = rng.uniform(20, 80) if sinful else rng.uniform(0, 30)
    return {"merit": round(merit, 1), "sin": round(sin, 1), "threads": []}


def karma_of(world, person: int) -> dict:
    entity = world.entity(person)
    if entity.data.get("karma") is not None:
        return entity.data["karma"]
    if entity.data.get("is_player"):
        return {"merit": 0.0, "sin": 0.0, "threads": []}
    return seeded(world, person)


def write(world, person: int, **changes) -> dict:
    karma = {**karma_of(world, person), **changes}
    world.update_data(person, karma=karma)
    return karma


def balance(world, person: int) -> float:
    k = karma_of(world, person)
    return round(k["merit"] - k["sin"], 1)


def add(world, person: int, merit: float = 0.0, sin: float = 0.0) -> None:
    k = karma_of(world, person)
    write(world, person, merit=round(k["merit"] + merit, 1), sin=round(k["sin"] + sin, 1))


def words(value: float) -> str:
    return next(word for bound, word in BALANCE_WORDS if value >= bound)


# --- deeds -----------------------------------------------------------------------------------------------------

def _counter(row: dict):
    def counted(world, event, event_id: int) -> None:
        if len(event.actors) > row["actor"] and world.entity(event.actors[row["actor"]]) is not None:
            add(world, event.actors[row["actor"]], merit=row.get("merit", 0), sin=row.get("sin", 0))
    return counted


for _kind, _row in DEEDS.items():
    listen(_kind)(_counter(_row))


@listen("duel_ended")
def _verdict(world, event, event_id: int) -> None:
    d = event.data
    if d.get("result") == "won" and d.get("by") == "player" and d.get("verdict") in VERDICTS \
            and not world.entity(event.actors[1]).data.get("beast"):
        side, amount = VERDICTS[d["verdict"]]
        add(world, event.actors[0], **{side: amount})


def _yielded(world, killer: int, victim: int) -> bool:
    """Whether the victim had yielded: the duel that ended in this killing ended on a yield."""
    return any(e.kind == "duel_ended" and e.actors[:2] == (killer, victim) and e.data.get("reason") == "yielded"
               for e in world.chronicle_about(victim, limit=3))


@listen("died")
def _killing(world, event, event_id: int) -> None:
    killer, victim = event.actors[0], event.actors[-1]
    if killer == victim or not world.entity(killer).data.get("is_player"):
        return
    dead = world.entity(victim)
    if dead.data.get("beast"):
        return
    if balance(world, victim) < WICKED:
        add(world, killer, merit=KILL_WICKED_MERIT)
    elif _yielded(world, killer, victim) or dead.data.get("realm", "mortal") == "mortal":
        add(world, killer, sin=KILL_INNOCENT_SIN)
    else:
        add(world, killer, sin=KILL_SIN)
