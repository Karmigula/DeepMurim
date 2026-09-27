"""Running your sect (phase 3c spec 5, 7): roster, teaching, elders, duty, buildings, treasury, pacts, the end."""

import systems.founding as founding
from systems import factions as F
from systems.attitude import attitude
from systems.beliefs import apparent_to
from systems.facts import make_variant, place_name, record_fact
from systems.membership import left_events, set_membership
from systems.realms import realm_index
from systems.standing import HARMFUL, knowledge_about
from systems.techniques import known_arts, martial_arts, teach
from world.events import Event, Witness, effect, listen
from world.gen.materialize import ensure_town, region_of
from world.gen.region import region_spec
from world.seed import rng_for

MAX_DISCIPLES, MAX_ELDERS = 12, 3
BUILDINGS = {"training_yard": (150, 10), "library": (200, 10), "infirmary": (150, 10),
             "guest_hall": (100, 5), "walls": (300, 15), "herb_garden": (250, 10), "pill_hall": (300, 15)}
SEASON = 360
HARM = HARMFUL
PACT_FLOOR = 0.6


def members(world, sect: int, roles=("disciple", "elder")) -> list[int]:
    out = []
    for person in F.members_of(world, sect):
        found = F.membership(world, person, sect)
        if found and found[1].get("role") in roles:
            out.append(person)
    return sorted(out)


def sect_of_member(world, player: int, person: int) -> int | None:
    sect = founding.my_sect(world, player)
    return sect if sect is not None and person in members(world, sect) else None


def can_invite(world, npc: int, player: int) -> bool:
    sect = founding.my_sect(world, player)
    entity = world.entity(npc)
    if sect is None or entity.data.get("is_player") or entity.data.get("beast") or entity.data.get("sworn_to"):
        return False
    if F.memberships(world, npc) or len(members(world, sect, ("disciple",))) >= MAX_DISCIPLES:
        return False
    return attitude(world, npc, apparent_to(world, npc, player)).score > -0.3


def invite_events(world, player: int, npc: int, place: int) -> list[Event]:
    sect = founding.my_sect(world, player)
    roll = rng_for(world.world_seed, f"invite:{npc}:{player}:{world.time}").random()
    accepted = roll < founding.follow_chance(world, npc, player, place)
    witness = Witness(npc, "respect" if accepted else "annoyed", 0.3 if accepted else 0.2)
    return [Event("sect_invite", (player, npc), place, {"sect": sect, "accepted": accepted}, witnesses=(witness,))]


@effect("sect_invite")
def _invited(world, event) -> None:
    if event.data["accepted"]:
        founding.enrol(world, event.actors[1], event.data["sect"], 50)


def teachable_to(world, player: int, person: int) -> list[int]:
    known = {a.technique.id for a in known_arts(world, person)}
    return [a.technique.id for a in martial_arts(world, player) if a.technique.id not in known]


def teach_events(world, player: int, person: int, technique: int, place: int) -> list[Event]:
    sect = founding.my_sect(world, player)
    return [Event("sect_teach", (player, person), place,
                  {"sect": sect, "technique": technique, "name": world.entity(technique).name})]


@effect("sect_teach")
def _taught(world, event) -> None:
    player, person, d = event.actors[0], event.actors[1], event.data
    teach(world, person, d["technique"], source="sect", teacher=player)
    arts = list(world.entity(d["sect"]).data.get("arts", []))
    if d["technique"] not in arts and len(arts) < 3:
        world.update_data(d["sect"], arts=[*arts, d["technique"]])


def elder_block(world, sect: int, person: int) -> str | None:
    if len(members(world, sect, ("elder",))) >= MAX_ELDERS:
        return "Your sect already has three elders."
    rank = F.membership(world, person, sect)[0]
    if rank < 2 and realm_index(world.entity(person).data.get("realm", "mortal")) < 1:
        return "They are not ready to be an elder."
    if world.entity(person).data.get("loyalty", 0) < 60:
        return "They are not loyal enough."
    return None


def elder_events(world, player: int, person: int, place: int) -> list[Event]:
    return [Event("sect_elder", (player, person), place, {"sect": founding.my_sect(world, player)})]


@effect("sect_elder")
def _elder(world, event) -> None:
    set_membership(world, event.actors[1], event.data["sect"], rank=3, role="elder")


def duty_events(world, player: int, person: int, place: int, on: bool) -> list[Event]:
    return [Event("sect_duty", (player, person), place, {"sect": founding.my_sect(world, player), "on": on})]


@effect("sect_duty")
def _duty(world, event) -> None:
    person, d = event.actors[1], event.data
    seat = world.entity(d["sect"]).data["seat"]
    world.update_data(person, on_duty=d["on"])
    world.unrelate(person, "located_in")
    world.relate(person, region_of(world, seat).id if d["on"] else seat, "located_in")


def expel_events(world, player: int, person: int, place: int) -> list[Event]:
    sect = founding.my_sect(world, player)
    return [Event("sect_expel", (player, person), place, {"sect": sect},
                  witnesses=(Witness(person, "wronged", 0.8),))] + left_events(world, person, sect, place, "expelled")


def built(world, sect: int, name: str) -> bool:
    return bool(world.entity(sect).data.get("buildings", {}).get(name, {}).get("built"))


def build_block(world, sect: int, name: str) -> str | None:
    if name not in BUILDINGS:
        return "There is no such building."
    if name in world.entity(sect).data.get("buildings", {}):
        return "That is already built or being built."
    treasury, cost = world.entity(sect).data["treasury"], BUILDINGS[name][0]
    if treasury < cost:
        return f"The treasury holds {treasury} silver; that costs {cost}."
    return None


def build_events(world, player: int, name: str, place: int) -> list[Event]:
    sect = founding.my_sect(world, player)
    return [Event("sect_build", (player,), place, {"sect": sect, "building": name, "cost": BUILDINGS[name][0]})]


@effect("sect_build")
def _build(world, event) -> None:
    d = event.data
    data = world.entity(d["sect"]).data
    buildings = {**data.get("buildings", {}), d["building"]: {"done_at": world.time + SEASON, "built": False}}
    world.update_data(d["sect"], treasury=data["treasury"] - d["cost"], buildings=buildings)


def treasury_events(world, player: int, place: int, amount: int) -> list[Event]:
    """Positive deposits your silver; negative withdraws from the treasury."""
    return [Event("sect_treasury", (player,), place, {"sect": founding.my_sect(world, player), "amount": amount})]


@effect("sect_treasury")
def _treasury(world, event) -> None:
    player, d = event.actors[0], event.data
    silver = int(world.entity(player).data.get("silver", 0))
    world.update_data(player, silver=silver - d["amount"])
    world.update_data(d["sect"], treasury=world.entity(d["sect"]).data["treasury"] + d["amount"])


def has_pact(world, sect: int, other: int) -> bool:
    return other in world.targets(sect, "pact")


def sect_stance(world, other: int, sect: int, roster: list[int] | None = None) -> float:
    """How another faction regards your sect: the founding stance, moved by what its towns heard your people do."""
    value = F.stance(world, other, sect)
    harm = help_ = 0
    if roster is None:
        roster = [world.entity(sect).data["founder"], *members(world, sect)]
    for person in roster:
        know, _ = knowledge_about(world, other, person)
        for belief, fact in know:
            target = belief.variant.get("target")
            if fact.predicate not in HARM or not isinstance(target, int):
                continue
            theirs = [f for f, _, d in F.memberships(world, target) if d.get("status", "member") == "member"]
            if other in theirs:
                harm += 1
            elif any(F.stance(world, other, g) <= F.HOSTILE for g in theirs):
                help_ += 1
    value = max(-1.0, min(1.0, value - 0.1 * harm + 0.05 * help_))
    return max(value, PACT_FLOOR) if has_pact(world, sect, other) else round(value, 3)


def stance_word(value: float, pact: bool = False) -> str:
    if pact:
        return "allied"
    if value >= 0.3:
        return "friendly"
    if value > -0.3:
        return "neutral"
    if value > -0.6:
        return "hostile"
    return "enemy"


def pact_events(world, player: int, recruiter: int, other: int, place: int) -> list[Event]:
    return [Event("allied_with", (player, recruiter), place, {"sect": founding.my_sect(world, player), "other": other})]


@effect("allied_with")
def _allied(world, event) -> None:
    sect, other = event.data["sect"], event.data["other"]
    world.relate(sect, other, "pact")
    world.relate(other, sect, "pact")
    value = max(F.stance(world, sect, other), PACT_FLOOR)
    world.relate(sect, other, "stance", value)
    world.relate(other, sect, "stance", value)


@listen("allied_with")
def _allied_fact(world, event, event_id: int) -> None:
    sect, other = event.data["sect"], event.data["other"]
    record_fact(world, sect, "allied_with", other, place=event.place, source_event=event_id, weight=1.5,
                variant=make_variant("allied_with", sect, other, place=place_name(world, event.place)))


def disband_events(world, player: int, place: int) -> list[Event]:
    return [Event("sect_dissolved", (player,), place, {"sect": founding.my_sect(world, player), "reason": "disbanded"})]


def dissolve(world, sect: int) -> None:
    for person in world.sources(sect, "member_of"):
        found = F.membership(world, person, sect)
        if found and found[1].get("status", "member") == "member":
            set_membership(world, person, sect, status="released")
            if world.entity(person).data.get("on_duty"):  # home from the road, to a seat that is no more
                world.update_data(person, on_duty=False)
                world.unrelate(person, "located_in")
                world.relate(person, world.entity(sect).data["seat"], "located_in")
    data = world.entity(sect).data
    seat = world.entity(data["seat"]).data
    world.update_data(data["seat"], halls=[f for f in seat.get("halls", []) if f != sect],
                      seats=[f for f in seat.get("seats", []) if f != sect])
    world.update_data(sect, dissolved=True)
    if world.entity(data["founder"]).data.get("sect") == sect:
        world.update_data(data["founder"], sect=None)


@listen("died")
def _member_died(world, event, event_id: int) -> None:
    """A dead disciple is no longer a member (phase 3c spec 9.2)."""
    victim = event.actors[-1]
    for fid, _, data in F.memberships(world, victim):
        if world.entity(fid).data["type"] == "player_sect" and data.get("status", "member") == "member":
            set_membership(world, victim, fid, status="dead")


def elsewhere(world, seat: int) -> int:
    """Another town for someone leaving the seat: the next town in its region, or the region to the east."""
    d = world.entity(seat).data
    count = region_spec(world.world_seed, d["x"], d["y"]).town_count
    if count > 1:
        return ensure_town(world, d["x"], d["y"], (d["index"] + 1) % count)
    return ensure_town(world, d["x"] + 1, d["y"], 0)


def _left_the_sect(world, event, event_id: int) -> None:
    person, faction = event.actors[0], event.data["faction"]
    sect = world.entity(faction)
    if sect.data.get("type") != "player_sect" or person == sect.data.get("founder"):
        return
    world.update_data(person, on_duty=False)
    world.unrelate(person, "located_in")
    world.relate(person, elsewhere(world, sect.data["seat"]), "located_in")


for _kind in ("expelled", "deserted", "released"):
    listen(_kind)(_left_the_sect)


@effect("sect_dissolved")
def _dissolved(world, event) -> None:
    dissolve(world, event.data["sect"])


@listen("sect_dissolved")
def _dissolved_fact(world, event, event_id: int) -> None:
    player, sect = event.actors[0], event.data["sect"]
    record_fact(world, player, "sect_dissolved", sect, place=event.place, source_event=event_id, weight=2.0,
                variant=make_variant("sect_dissolved", player, sect, place=place_name(world, event.place)))
