"""Around the brackets (phase 4e spec 5.2-5.3): watching bouts, elders in the crowd, and the grudges of the beaten.

Watching a bout on its day settles it before your eyes: you learn a fragment of each fighter's art
and their stance, and you know them after. Each round's winner may be noticed by an elder of a sect
with a hall in town: a wanderer is taken in, you are invited (or, if already one of theirs, given a
gift). The beaten remember who beat them; the proud may take it as a wrong and seek revenge (4a).
"""

import systems.tournaments as T
from systems import factions as F
from systems import halls
from systems.duel import _add_fragment, fragment_of
from systems.opponent import tendency
from systems.purse import silver_of
from world.events import Event, Witness, effect
from world.seed import rng_for

NOTICE_BASE = 0.2
GRUDGE_CHANCE = 0.3
GIFT = (30, 80)
PROUD = frozenset({"proud", "hot-tempered"})


# --- watching --------------------------------------------------------------------------------------

def watchable(world, occurrence_id: int, player: int) -> tuple[int, int, dict] | None:
    """The next of today's bouts the player may watch at the venue (not their own)."""
    occurrence = world.entity(occurrence_id)
    if occurrence.data["place"] not in world.targets(player, "located_in"):
        return None
    today = T.day(occurrence, world.time)
    for r, matches in enumerate(occurrence.data["data"]["rounds"]):
        for i, m in enumerate(matches):
            if m["how"] is None and m["day"] == today and T.alive(world, m["a"]) and T.alive(world, m["b"])                     and player not in (m["a"], m["b"]):
                return r, i, m
    return None


def watch_events(world, occurrence_id: int, player: int) -> list[Event]:
    found = watchable(world, occurrence_id, player)
    if found is None:
        return []
    r, i, m = found
    occurrence = world.entity(occurrence_id)
    winner = T._sim_winner(world, occurrence, m["a"], m["b"], r, i)
    loser = m["b"] if winner == m["a"] else m["a"]
    rng = rng_for(world.world_seed, f"watch:{occurrence_id}:{r}:{i}")
    arts = occurrence.data["data"].get("arts") or {}
    fragments = [fragment_of(world, arts[str(p)], rng) for p in (m["a"], m["b"]) if arts.get(str(p)) is not None]
    tendencies = {str(p): tendency(tuple(world.entity(p).data.get("traits", ()))) for p in (m["a"], m["b"])}
    return [T.match_event(occurrence, r, i, winner, loser, "sim", T.day(occurrence, world.time), world),
            Event("watched", (player, m["a"], m["b"]), occurrence.data["place"],
                  {"occurrence": occurrence_id, "round": r, "match": i, "winner": winner, "fragments": fragments,
                   "tendencies": tendencies})]


@effect("watched")
def _watched(world, event) -> None:
    for fragment in event.data["fragments"]:
        _add_fragment(world, event.actors[0], fragment)


# --- grudges -----------------------------------------------------------------------------------------

def loser_witnesses(world, occurrence, winner, loser, key: str) -> tuple[Witness, ...]:
    """How the beaten remember it: humbled by a lesser fighter, or respectful of a better one; the proud,
    or a rival sect's fighter, may take it as a wrong (spec §5.3)."""
    if winner is None or loser is None or world.entity(loser).data.get("is_player"):
        return ()
    feeling = "humiliated" if T.realm_of(world, loser) > T.realm_of(world, winner) else "respect"
    proud = PROUD & set(world.entity(loser).data.get("traits", ()))
    rivals = not proud and T.watched(world, occurrence) and any(  # sect rivalry: weighed where the player sees
        F.stance(world, a, b) <= F.HOSTILE
        for a, _, _ in F.memberships(world, loser) for b, _, _ in F.memberships(world, winner) if a != b)
    if (proud or rivals) and rng_for(world.world_seed, f"grudge:{occurrence.id}:{key}").random() < GRUDGE_CHANCE:
        return (Witness(loser, "wronged", 0.8),)
    return (Witness(loser, feeling, 0.5),)


# --- elders in the crowd ------------------------------------------------------------------------------

def _elder_here(world, town: int, rng) -> tuple[int, int] | None:
    """(faction, elder) for a sect with a hall in town and an elder at it, chosen by seed."""
    found = []
    for faction in halls.halls_here(world, town):
        if world.entity(faction).data.get("type") in F.STAFFED:
            found += [(faction, e) for e in halls.staff_at(world, faction, town, roles=("elder", "leader"))]
    return rng.choice(sorted(found)) if found else None


def notice_events(world, occurrence, r: int, winner) -> list[Event]:
    """A round's winner may catch an elder's eye: later rounds, better odds (spec §5.2)."""
    t = occurrence.data["data"]
    if winner is None or not T.alive(world, winner) or not t["rounds"]:
        return []
    rng = rng_for(world.world_seed, f"notice:{occurrence.id}:{r}:{winner}")
    if rng.random() >= NOTICE_BASE * (r + 1) / len(t["rounds"]):
        return []
    found = _elder_here(world, occurrence.data["place"], rng)
    if found is None:
        return []
    faction, elder = found
    person = world.entity(winner)
    already = F.membership(world, winner, faction)
    if person.data.get("is_player"):
        from systems.membership import refusal  # the sect's own rules still hold; they reward what they cannot take
        offer = "gift" if already or refusal(world, winner, faction, occurrence.data["place"]) else "invite"
    elif already or any(world.entity(f).data.get("type") in F.MARTIAL for f, _, d in F.memberships(world, winner)
                        if d.get("status", "member") == "member"):
        return []
    else:
        offer = "join"
    return [Event("noticed", (elder, winner), occurrence.data["place"],
                  {"faction": faction, "offer": offer, "silver": rng.randint(*GIFT) if offer == "gift" else 0})]


@effect("noticed")
def _noticed(world, event) -> None:
    elder, person = event.actors
    d = event.data
    if d["offer"] == "join":
        world.relate(person, d["faction"], "member_of", 0, {"role": "disciple", "hall": None, "merit": 0,
                                                            "status": "member", "secret": False})
    elif d["offer"] == "invite":
        invitations = dict(world.entity(person).data.get("invitations", {}))
        invitations[str(d["faction"])] = elder
        world.update_data(person, invitations=invitations)
    else:
        world.update_data(person, silver=silver_of(world, person) + d["silver"])
