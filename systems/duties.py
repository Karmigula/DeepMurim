"""Duties (phase 3b spec 5): issued by a hall keeper, done in the world, rewarded in merit."""

import systems.encounters as encounters
from systems import factions as F
from systems import halls
from systems.attitude import afraid
from systems.beliefs import apparent_to
from systems.membership import set_membership
from world.events import Event, Witness, effect
from world.gen.materialize import ensure_region, ensure_town, people_at
from world.gen.region import region_spec
from world.seed import rng_for

KINDS = ("hunt", "deliver", "escort", "collect", "gather", "guard")
KIND_WEIGHTS = {
    "orthodox_sect": (3, 2, 0, 0, 1, 2), "school": (3, 2, 0, 0, 1, 2), "alliance": (3, 2, 0, 0, 1, 2),
    "demonic_cult": (3, 1, 0, 2, 1, 1), "unorthodox_clan": (3, 1, 0, 2, 1, 1), "bandit_fort": (3, 1, 0, 2, 1, 1),
    "martial_clan": (2, 2, 1, 2, 0, 2), "local_clan": (2, 2, 1, 2, 0, 2),
    "beggars": (0, 3, 0, 0, 3, 0), "merchant_guild": (1, 2, 3, 3, 1, 0), "imperial": (3, 1, 0, 1, 1, 2),
}
RAID_CHANCE = 0.3
WATCHES_PER_DAY = 4
REST_KINDS = frozenset({"rested", "cultivated", "practised"})


def open_duty(world, player: int):
    duty = world.entity(world.entity(player).data.get("duty") or 0)
    return duty if duty is not None and duty.data.get("status") == "open" else None


def _near(rng, here, radius: int) -> tuple[int, int, int]:
    dx, dy = rng.choice([(a, b) for a in range(-radius, radius + 1) for b in range(-radius, radius + 1) if (a, b) != (0, 0)])
    return here["x"] + dx, here["y"] + dy, max(abs(dx), abs(dy))


def _resident(world, rng, town: int, exclude: set) -> int | None:
    halls.settle_town(world, town)
    people = sorted(p.id for p in people_at(world, town) if p.id not in exclude and not p.data.get("is_player")
                    and not p.data.get("dead") and not p.data.get("beast") and not F.memberships(world, p.id))
    return rng.choice(people) if people else None


def _hostile_member(world, rng, faction: int) -> int | None:
    others = [f for f in F.ensure_roster(world) if f != faction and F.stance(world, faction, f) <= F.HOSTILE]
    others = others or [f for f in F.ensure_roster(world) if f != faction and F.is_martial(world, f)]
    if not others:
        return None
    rival = rng.choice(others)
    staff = halls.staff_at(world, rival, halls.seat_of(world, rival), roles=("disciple",))
    return rng.choice(staff) if staff else None


def issue_events(world, player: int, faction: int, keeper: int, place: int, kind: str | None = None,
                 release: bool = False) -> list[Event]:
    n = world.entity(player).data.get("duties_taken", 0)
    rng = rng_for(world.world_seed, f"duty:{faction}:{player}:{n}")
    ftype = world.entity(faction).data["type"]
    kind = kind or rng.choices(KINDS, weights=KIND_WEIGHTS[ftype])[0]
    here = world.entity(place).data
    rank = F.membership(world, player, faction)[0]
    data = {"faction": faction, "holder": player, "kind": kind, "target": None, "town": None, "region": None,
            "difficulty": min(3, rank + 1), "status": "open", "issued_at": world.time, "days": 0, "guarded": 0,
            "release": release, "n": n}
    regions = 1
    if kind == "hunt":
        x, y, regions = _near(rng, here, 2)
        region = world.entity(ensure_region(world, x, y))
        slot = encounters._free_roamer_slot(world, region)
        danger = encounters.region_danger(world.world_seed, x, y)
        data.update(region=[x, y], target=encounters.make_roamer(world, region, rng.choice(("bandit", "beast")), slot, danger))
    elif kind in ("deliver", "escort"):
        x, y, regions = _near(rng, here, 3 if kind == "deliver" else 2)
        data["town"] = ensure_town(world, x, y, rng.randrange(region_spec(world.world_seed, x, y).town_count))
    elif kind == "collect":
        x, y, regions = _near(rng, here, 2)
        town = ensure_town(world, x, y, rng.randrange(region_spec(world.world_seed, x, y).town_count))
        data.update(town=town, target=_resident(world, rng, town, {player}), amount=20 * data["difficulty"])
    elif kind == "gather":
        data["target"] = _hostile_member(world, rng, faction)
    elif kind == "guard":
        data.update(town=halls.seat_of(world, faction), days=5 * data["difficulty"])
    if kind in ("collect", "gather") and data["target"] is None:  # nobody fitting: carry a letter instead
        return issue_events(world, player, faction, keeper, place, kind="deliver", release=release)
    days = data["days"] + 7 if kind == "guard" else 3 * regions + 7
    data["deadline"] = world.time + days * WATCHES_PER_DAY
    target = data["target"] if kind in ("collect", "gather") else None
    return [Event("duty_issued", (player, keeper) + ((target,) if target else ()), place, data)]


@effect("duty_issued")
def _issued(world, event) -> None:
    d = dict(event.data)
    duty = world.add_entity("duty", f"{d['kind']} for #{d['faction']}", d)
    player = event.actors[0]
    world.update_data(player, duty=duty, duties_taken=d["n"] + 1)


def progress(world, player: int):
    """'done', 'failed' or None for the open duty, from the state of the world."""
    duty = open_duty(world, player)
    if duty is None:
        return None
    d = duty.data
    target = world.entity(d["target"]) if d.get("target") else None
    if d["kind"] == "hunt" and target is not None:
        for entry in world.chronicle_about(target.id, limit=20):
            if entry.kind == "duel_ended" and entry.time >= d["issued_at"] and entry.actors[0] == player \
                    and entry.data.get("result") == "won":
                needs_kill = world.entity(d["faction"]).data["path"] == "ruthless"
                if not needs_kill or entry.data.get("verdict") == "kill":
                    return "done"
    if target is not None and target.data.get("dead"):
        return "failed"
    if world.time > d["deadline"]:
        return "failed"
    if d["kind"] in ("deliver", "escort") and d["town"] in world.targets(player, "located_in"):
        return "done"
    if d["kind"] == "collect" and d.get("paid"):
        return "done"
    if d["kind"] == "gather":
        if any(b.learned_at >= d["issued_at"] and d["target"] in (b.variant.get("actor"), b.variant.get("target"))
               for b in world.beliefs(player)):
            return "done"
    if d["kind"] == "guard" and d["guarded"] >= d["days"]:
        return "done"
    return None


def done_events(world, player: int, place: int, reason: str = "done") -> list[Event]:
    duty = open_duty(world, player)
    d = duty.data
    sponsor = F.membership(world, player, d["faction"])[1].get("sponsor")
    witnesses = (Witness(sponsor, "respect", 0.3),) if sponsor else ()
    return [Event("duty_done", (player,), place, {"duty": duty.id, "faction": d["faction"], "kind": d["kind"],
                                                  "merit": 10 * d["difficulty"], "silver": 5 * d["difficulty"],
                                                  "release": d.get("release", False)}, witnesses=witnesses)]


def failed_events(world, player: int, place: int, reason: str = "late") -> list[Event]:
    duty = open_duty(world, player)
    d = duty.data
    sponsor = F.membership(world, player, d["faction"])[1].get("sponsor")
    witnesses = (Witness(sponsor, "annoyed", 0.3),) if sponsor else ()
    return [Event("duty_failed", (player,), place, {"duty": duty.id, "faction": d["faction"], "kind": d["kind"],
                                                    "reason": reason}, witnesses=witnesses)]


@effect("duty_done")
def _done(world, event) -> None:
    player, d = event.actors[0], event.data
    _, data = F.membership(world, player, d["faction"])
    set_membership(world, player, d["faction"], merit=data.get("merit", 0) + d["merit"])
    world.update_data(player, silver=int(world.entity(player).data.get("silver", 0)) + d["silver"], duty=None)
    world.update_data(d["duty"], status="done")


@effect("duty_failed")
def _failed(world, event) -> None:
    player, d = event.actors[0], event.data
    _, data = F.membership(world, player, d["faction"])
    set_membership(world, player, d["faction"], merit=max(0, data.get("merit", 0) - 10))
    world.update_data(player, duty=None)
    world.update_data(d["duty"], status="failed")


def hunt_encounter(world, player: int, town, rng):
    """A hunt's quarry waits on the roads of its region."""
    duty = open_duty(world, player)
    if duty is None or duty.data["kind"] != "hunt":
        return None
    if [town.data["x"], town.data["y"]] != duty.data["region"]:
        return None
    target = world.entity(duty.data["target"])
    if target is None or target.data.get("dead"):
        return None
    kind = target.data.get("roamer_kind", "bandit")
    return encounters.encounter_events(player, target.id, town.id, kind, 5 if kind == "bandit" else 0)


def escort_encounter(world, player: int, town, rng):
    """A caravan draws twice the trouble: a second chance at a road encounter."""
    duty = open_duty(world, player)
    if duty is None or duty.data["kind"] != "escort":
        return None
    second = rng_for(world.world_seed, f"escort:{player}:{world.time}")
    danger = encounters.region_danger(world.world_seed, town.data["x"], town.data["y"])
    if second.random() >= danger * encounters.ENCOUNTER_CHANCE:
        return None
    return encounters.random_encounter(world, player, town, second)


def pays_willingly(world, debtor: int, player: int) -> bool:
    traits = set(world.entity(debtor).data.get("traits", ()))
    return bool(traits & {"honest", "kind"}) or afraid(world, debtor, apparent_to(world, debtor, player))


def debt_events(player: int, debtor: int, place: int, duty: int, amount: int) -> list[Event]:
    return [Event("debt_paid", (player, debtor), place, {"duty": duty, "amount": amount})]


@effect("debt_paid")
def _paid(world, event) -> None:
    world.update_data(event.data["duty"], paid=True)


def raid_due(world, player: int, event_id: int, event) -> bool:
    duty = open_duty(world, player)
    if duty is None or duty.data["kind"] != "guard" or event.kind not in REST_KINDS or event.place != duty.data["town"]:
        return False
    return rng_for(world.world_seed, f"raid:{duty.id}:{event_id}").random() < RAID_CHANCE


def raider(world, duty, town: int) -> int:
    """A seeded raider of a faction hostile to the duty's, standing in the seat."""
    rng = rng_for(world.world_seed, f"raider:{duty.id}:{world.time}")
    enemy = _hostile_member(world, rng, duty.data["faction"])
    if enemy is not None:
        world.unrelate(enemy, "located_in")
        world.relate(enemy, town, "located_in")
        return enemy
    person = world.add_entity("person", "a masked raider", {"realm": world.entity(duty.data["holder"]).data.get("realm", "mortal"),
                                                            "occupation": "raider", "traits": ["hot-tempered", "proud"]})
    world.relate(person, town, "located_in")
    return person


def guarded_events(world, player: int, event) -> None:
    """Count days spent resting at the seat toward a guard duty (called by the engine)."""
    duty = open_duty(world, player)
    if duty is not None and duty.data["kind"] == "guard" and event.kind in REST_KINDS and event.place == duty.data["town"]:
        world.update_data(duty.id, guarded=duty.data["guarded"] + int(event.data.get("days", 0)))


encounters.ROAD_HOOKS.extend([hunt_encounter, escort_encounter])
