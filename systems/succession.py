"""Succession (phase 4b spec 5): the heir takes up your wealth, your arts and your name, and becomes you."""

import systems.bonds as bonds
import systems.lives as lives
from systems import factions as F
from systems.facts import make_variant, place_name, record_fact
from systems.founding import followers, my_sect
from systems.goods import MULE_CAPACITY, capacity, carried, fit
from systems.membership import set_membership
from systems.purse import silver_of
from systems.techniques import known_arts, martial_arts, teach
from world.events import Event, effect, listen
from world.gen.materialize import ensure_town, region_of
from world.gen.region import region_spec
from world.seed import rng_for

SILVER = {"named": 1.0, "child": 1.0, "disciple": 0.75, "sibling": 0.5, "follower": 0.5}
ARTS = {"named": 0.7, "child": 0.7, "disciple": 0.7, "sibling": 0.5, "follower": 0.3}


def heir_kind(world, player: int, heir: int) -> str | None:
    return dict(bonds.candidates(world, player)).get(heir)


def _home_town(world, heir: int, sect: int | None) -> int:
    """Where the heir wakes: where they are, or the sect's seat if they are away on the roads (ruling 5)."""
    here = lives.home(world, heir)
    entity = world.entity(here) if here is not None else None
    if entity is not None and entity.kind == "town":
        return here
    if sect is not None:
        return world.entity(sect).data["seat"]
    region = entity if entity is not None and entity.kind == "region" else None
    x, y = (region.data["x"], region.data["y"]) if region is not None else (0, 0)
    return ensure_town(world, x, y, 0)


def succession_events(world, player: int, heir: int) -> list[Event]:
    lives.catch_up(world, heir)  # the heir has lived their own seasons, whatever the player missed
    kind = heir_kind(world, player, heir)
    if kind is None:
        return []
    silver = int(silver_of(world, player) * SILVER[kind])
    theirs = {a.technique.id: a.completeness for a in known_arts(world, heir)}
    arts = []
    for art in martial_arts(world, player):
        completeness = round(min(1.0, art.completeness * ARTS[kind]), 3)
        if theirs.get(art.technique.id, 0.0) < completeness:
            arts.append([art.technique.id, completeness])
    home = _home_town(world, heir, my_sect(world, player))
    mule = bool(world.entity(player).data.get("mule")) and not world.entity(heir).data.get("mule")
    pack = carried(world, heir)
    for good, n in carried(world, player).items():
        pack[good] = pack.get(good, 0) + n
    goods, _ = fit(pack, capacity(world, heir) + (MULE_CAPACITY if mule else 0))  # the rest is lost at the grave
    return [Event("succession", (player, heir), home, {"kind": kind, "silver": silver, "arts": arts, "home": home,
                                                       "goods": goods, "mule": mule})]


def newcomer_town(world, old: int) -> int:
    """A town within 3 regions of where the old player fell (spec §5.3)."""
    grave = world.targets(old, "buried_at")
    region = region_of(world, grave[0]) if grave and world.entity(grave[0]).kind == "town" else None
    x, y = (region.data["x"], region.data["y"]) if region is not None else (0, 0)
    rng = rng_for(world.world_seed, f"newcomer:{old}")
    x, y = x + rng.randint(-3, 3), y + rng.randint(-3, 3)
    return ensure_town(world, x, y, rng.randrange(region_spec(world.world_seed, x, y).town_count))


@effect("succession")
def _succession(world, event) -> None:
    old, heir = event.actors
    d = event.data
    world.update_data(heir, silver=silver_of(world, heir) + d["silver"])
    world.update_data(old, silver=0)
    if "goods" in d:  # the pack and the mule pass to the heir (phase 4c final review)
        world.update_data(heir, goods=d["goods"], **({"mule": True} if d["mule"] else {}))
        world.update_data(old, goods={}, mule=False)
    for item in world.targets(old, "owns"):
        world.unrelate(old, "owns", item)
        world.relate(heir, item, "owns")
        if world.entity(item).kind == "mask":
            world.update_data(item, persona=None)  # a new wearer is a new face (phase 4b review)
    for town in world.targets(old, "owns_land"):
        world.unrelate(old, "owns_land", town)
        world.relate(heir, town, "owns_land")
        if world.entity(town).data.get("owner") == old:
            world.update_data(town, owner=heir)
    for fid, rank, data in F.memberships(world, heir):  # the player holds no post in an NPC faction
        if world.entity(fid).data["type"] != "player_sect" and data.get("status", "member") == "member" \
                and data.get("role") not in (None, "member"):
            set_membership(world, heir, fid, rank=min(rank, 3), status="released")
    sect = my_sect(world, old)
    if sect is not None:
        for fid, _, data in F.memberships(world, heir):
            kind = world.entity(fid).data["type"]
            if fid != sect and kind in F.MARTIAL and data.get("status", "member") == "member" and not data.get("secret"):
                set_membership(world, heir, fid, status="released")  # the heir renounces another martial faction
        world.relate(heir, sect, "member_of", 4,
                     {"role": "leader", "hall": None, "merit": 0, "status": "member", "secret": False})
        world.update_data(sect, founder=heir)
        world.update_data(old, sect=None)
        world.update_data(heir, sect=sect)
    practised = {a.technique.id: a.mastery for a in known_arts(world, heir)}
    for technique, completeness in d["arts"]:
        teach(world, heir, technique, completeness=completeness, known_completeness=completeness,
              source="inheritance", teacher=old, mastery=practised.get(technique, 0.05))
    for follower in followers(world, old):
        if follower != heir:
            world.update_data(follower, sworn_to=heir)  # they served the house, and serve its heir
    if lives.home(world, heir) != d["home"]:
        world.unrelate(heir, "located_in")
        world.relate(heir, d["home"], "located_in")
    ancestors = list(world.entity(old).data.get("ancestors", [])) + [old]
    world.update_data(old, is_player=False, death=world.entity(old).data.get("dying"), dying=None, named_heir=None)
    world.update_data(heir, is_player=True, ancestors=ancestors, sworn_to=None, on_duty=False,
                      age=float(world.entity(heir).data.get("age", 18)))
    world.set_meta("player_id", heir)


@listen("succession")
def _heir_news(world, event, event_id: int) -> None:
    old, heir = event.actors
    record_fact(world, heir, "heir_of", old, place=event.place, source_event=event_id, weight=2.0,
                variant=make_variant("heir_of", heir, old, place=place_name(world, event.place)))
