"""What formations do (phase 5d spec 5): the gate and the garden of a sect, a fight inside an array, a hidden
hero, and a warded seclusion.

Each is a small factor read where the rule already lives: 3c's gate, 5c's theft, 2b's fighters and fleeing, 2b's
challengers and 3b's hunters, and 2a's meditation. Nothing here writes: a formation's strength is read from the
place it was laid (`formations.laid`).
"""

from systems import factions as F
from systems.formations import strength
from world.seed import rng_for

GATE_CUT, GATE_FIGHT = 0.5, 0.2       # the Heavenly Gate: fewer challengers, stronger defenders
WARD_CUT = 0.3                        # the Veiled Garden: a thief's chance, less this x strength
BATTLE = 0.2                          # confusion weakens foes, killing strengthens the owner, by this x strength
SECLUSION_GAIN, SECLUSION_DEVIATION = 0.2, 0.5


def _here(world, person: int):
    found = world.targets(person, "located_in")
    return found[0] if found else None


# --- a sect's defences (spec 5.1) ----------------------------------------------------------------------------

def gate_factor(world, seat: int) -> float:
    """How much of 3c's gate chance a Heavenly Gate array at the seat leaves."""
    return 1.0 - GATE_CUT * strength(world, seat, "heavenly_gate")


def npc_ward(world, faction: int) -> float:
    """A great sect's own seeded ward over its garden and hall, 0-1."""
    data = world.entity(faction).data
    if data.get("tier") != "great" or data.get("type") == "player_sect":
        return 0.0
    return round(rng_for(world.world_seed, f"ward:{faction}").random(), 2)


def theft_cut(world, faction: int) -> float:
    """What a sect's ward takes off a thief's chance (5c): the laid Veiled Garden, or its own."""
    seat = world.entity(faction).data.get("seat")
    laid = strength(world, seat, "veiled_garden") if seat is not None else 0.0
    return WARD_CUT * max(laid, npc_ward(world, faction))


# --- a fight inside an array (spec 5.2) ---------------------------------------------------------------------------

def _owners(world, place, key: str) -> list[tuple[int, float]]:
    from systems.formations import laid
    return [(f["owner"], f["strength"]) for f in laid(world, place, key)]


def fight_factor(world, person: int) -> float:
    """What the arrays where this person stands make of their strength: the owner's Killing array lifts them,
    another's Confusion array weakens them; a sect's own gate array lifts its defenders."""
    place = _here(world, person)
    entity = world.entity(place) if place is not None else None
    if entity is None or not entity.data.get("formations"):
        return 1.0  # most places hold none: nothing more is read
    factor = 1.0
    for owner, s in _owners(world, place, "killing"):
        if owner == person:
            factor *= 1 + BATTLE * s
    for owner, s in _owners(world, place, "confusion"):
        if owner != person:
            factor *= 1 - BATTLE * s
    gate = strength(world, place, "heavenly_gate")
    if gate and any(world.entity(f).data.get("seat") == place and d.get("status", "member") == "member"
                    for f, _, d in F.memberships(world, person)):
        factor *= 1 + GATE_FIGHT * gate
    return round(factor, 4)


def held(world, runner: int) -> bool:
    """Whether a Binding array here holds this runner fast: laid by anyone but them."""
    place = _here(world, runner)
    return any(owner != runner for owner, _ in _owners(world, place, "binding")) if place is not None else False


# --- concealment and seclusion (spec 5.3) --------------------------------------------------------------------------

def concealed(world, person: int, place) -> bool:
    """No avenger, rival or bounty hunter finds one hidden by their own Concealment array here."""
    return place is not None and strength(world, place, "concealment", owner=person) > 0


def cultivation_factor(world, person: int, place) -> float:
    return 1 + SECLUSION_GAIN * strength(world, place, "seclusion", owner=person)


def deviation_factor(world, person: int, place) -> float:
    return SECLUSION_DEVIATION if strength(world, place, "seclusion", owner=person) > 0 else 1.0
