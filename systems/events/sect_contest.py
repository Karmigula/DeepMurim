"""A sect's yearly contest (phase 4e spec 3): its disciples fight for rank, merit and a master's eye."""

import systems.tournaments as T
from systems import factions as F
from systems.facts import make_variant, place_name, record_fact
from systems.membership import set_membership
from systems.ranks import TOP_RANK
from world.events import Event, effect, listen
from world.seed import rng_for

SIZE, ROUND_DAYS = 8, (1, 1, 1)
MIN_DISCIPLES = 4
MERIT = 20
NOTICE_CHANCE = 0.5


def _faction_at(world, seat: int) -> int | None:
    found = sorted(f.id for f in world.entities("faction") if f.data.get("seat") == seat
                   and not f.data.get("dissolved") and f.data.get("type") in F.STAFFED | {"player_sect"})
    return found[0] if found else None


def _members(world, faction: int, roles) -> list[int]:
    """Living members in good standing with one of these roles: one query of the faction's relations."""
    return sorted(p for p, _, d in world.relations_to(faction, "member_of")
                  if d.get("status", "member") == "member" and d.get("role") in roles and T.alive(world, p))


def _disciples(world, faction: int) -> list[int]:
    return _members(world, faction, ("disciple", "member"))


def places(world, n: int, rng) -> list[int]:
    """Every sect's seat; `eligible` then asks, of the seats whose turn it is, for enough disciples."""
    return sorted({f.data["seat"] for f in world.entities("faction")
                   if f.data.get("seat") is not None and not f.data.get("dissolved")})


def eligible(world, seat: int, n: int) -> bool:
    faction = _faction_at(world, seat)
    return faction is not None and len([p for p in _disciples(world, faction)
                                        if not world.entity(p).data.get("is_player")]) >= MIN_DISCIPLES


def start_data(world, seat: int, n: int, rng) -> dict | None:
    faction = _faction_at(world, seat)
    if faction is None:
        return None
    name = world.entity(faction).name
    return T.start_data("sect_contest", SIZE, ROUND_DAYS, 0, f"First of the {name}'s contest of year {n // 4 + 1}",
                        T.edition(world, "sect_contest"), faction=faction)


def qualifies(world, occurrence, person: int, slack: int = 0) -> bool:
    found = F.membership(world, person, occurrence.data["data"]["faction"])
    return found is not None and found[1].get("status", "member") == "member"


def invite(world, occurrence) -> list[int]:
    faction = occurrence.data["data"]["faction"]
    return [p for p in _disciples(world, faction) if not world.entity(p).data.get("is_player")]


def rewards(world, occurrence, champion) -> list[Event]:
    """Merit and a rank step for the winner; perhaps an elder's notice (spec §3)."""
    if champion is None:
        return []
    faction = occurrence.data["data"]["faction"]
    rank, data = F.membership(world, champion, faction)
    events = [Event("contest_rewarded", (champion,), occurrence.data["place"],
                    {"faction": faction, "merit": data.get("merit", 0) + MERIT, "rank": min(TOP_RANK, rank + 1)})]
    elders = _members(world, faction, ("elder",))
    youth = world.entity(champion)
    if elders and not youth.data.get("is_player") and float(youth.data.get("age", 30)) <= 30 \
            and rng_for(world.world_seed, f"contest:{occurrence.id}:notice").random() < NOTICE_CHANCE:
        events.append(Event("apprenticed", (elders[0], champion), occurrence.data["place"],
                            {"season": world.time // T.W.SEASON}))
    return events


@effect("contest_rewarded")
def _rewarded(world, event) -> None:
    d = event.data
    set_membership(world, event.actors[0], d["faction"], rank=d["rank"], merit=d["merit"])


def summary(world, seat: int, n: int, rng) -> list[Event]:
    """A contest far from the player (plan ruling 9): a champion by lot, weighted by realm, and their reward."""
    faction = _faction_at(world, seat)
    field = _disciples(world, faction) if faction is not None else []
    field = [p for p in field if not world.entity(p).data.get("is_player")]
    if not field:
        return []
    champion = rng.choices(field, weights=[1 + T.realm_of(world, p) for p in field])[0]
    title = f"First of the {world.entity(faction).name}'s contest of year {n // 4 + 1}"
    rank, data = F.membership(world, champion, faction)
    return [Event("contest_summarized", (champion,), seat, {"faction": faction, "title": title}),
            Event("contest_rewarded", (champion,), seat,
                  {"faction": faction, "merit": data.get("merit", 0) + MERIT, "rank": min(TOP_RANK, rank + 1)})]


@effect("contest_summarized")
def _summarized(world, event) -> None:
    champion = world.entity(event.actors[0])
    world.update_data(champion.id, titles=list(champion.data.get("titles", [])) + [event.data["title"]])


@listen("contest_summarized")
def _summarized_news(world, event, event_id: int) -> None:
    champion = event.actors[0]
    variant = make_variant("won_tournament", champion, None, place=place_name(world, event.place))
    variant.update(kind="sect_contest", title=event.data["title"])
    record_fact(world, champion, "won_tournament", None, place=event.place, source_event=event_id,
                weight=T.KIND_WEIGHT["sect_contest"], variant=variant)


def on_stage(world, occurrence, stage: str) -> list:
    return T.on_stage(world, occurrence, stage, invite)


def on_observe(world, occurrence) -> list:
    return T.on_observe(world, occurrence)
