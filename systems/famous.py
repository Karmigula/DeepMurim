"""Famous weapons (phase 5a spec 3.3): named blades with a legend, their keepers, how they pass, the Chronicle.

A great sect's master holds its treasure; a clan keeps its heirloom (or has lost it); a wandering master carries a
blade of their own through each city. They are items from the start, listed in the meta row `famous_weapons`.
They pass at a death to the killer, else the heir, else they lie where the dead fell. An heirloom given back to
its clan wins the clan's lasting favour. Each spring the Pavilion ranks them in the Hundred Weapons Chronicle.
"""

import systems.gear as gear
import systems.provenance as P
import systems.world_clock as world_clock
from systems import factions as F
from systems.claimants import staff
from systems.facts import make_variant, place_name, record_fact
from systems.realms import realm_index
from systems.kin import kin_of
from world.events import Event, Witness, commit, effect, listen
from world.gen.materialize import people_at
from world.seed import rng_for

NAMES = ("Frost Moon", "Nine Dragons", "Azure Cloud", "Blood Lotus", "Heaven Splitting", "Silent Thunder",
         "Jade Serpent", "Crimson Phoenix", "Northern Star", "White Tiger", "Black Tortoise", "Soul Reaving",
         "Autumn Water", "Burning Sun", "Falling Snow", "Seven Stars", "Iron Lotus", "Thousand Autumns",
         "Wandering Cloud", "Moonless Night")
FORM_WORDS = {"sword": "Sword", "saber": "Saber", "spear": "Spear", "staff": "Staff"}
CLANS = frozenset({"martial_clan", "local_clan"})
LOST_HEIRLOOM = 0.3
DIVINE_CHANCE = 0.25
HEIRLOOM_STANCE = 0.3
CHRONICLE_SIZE, TOP = 100, 10
FAMED_VICTIM = frozenset({"leader"})


# --- the index -------------------------------------------------------------------------------------------

def famous_weapons(world) -> list[int]:
    return list(world.get_meta("famous_weapons") or [])


def _name(world, rng, form: str) -> str:
    used = {world.entity(i).name for i in famous_weapons(world)}
    for _ in range(20):
        name = f"the {rng.choice(NAMES)} {FORM_WORDS[form]}"
        if name not in used:
            return name
    return f"the {rng.choice(NAMES)} {FORM_WORDS[form]} of {rng.randint(2, 99)}"


def make_famous(world, key: str, form: str, owner: int | None, how: str, legend: str, place,
                heirloom_of: int | None = None, name: str | None = None, grade: int | None = None) -> int:
    """A named weapon, famous from the start, with its founding legend told (spec 3.3)."""
    rng = rng_for(world.world_seed, f"famous:{key}")
    grade = grade if grade is not None else (4 if rng.random() < DIVINE_CHANCE else 3)
    item = gear.make_item(world, "weapon", form, grade, owner, how, name=name or _name(world, rng, form),
                          path=f"famous:{key}", famous=True, heirloom_of=heirloom_of, claimed_by=heirloom_of,
                          lost_at=None if owner is not None else place)
    world.set_meta("famous_weapons", famous_weapons(world) + [item])
    if owner is None:
        world.set_meta("famous_lying", (world.get_meta("famous_lying") or []) + [item])
    if owner is not None:
        world.unrelate(owner, "wields")
        world.relate(owner, item, "wields")
        carried = dict(gear.carried(world, owner))
        carried["weapon"] = None  # the famous blade is what they carry: no second one in their seeded gear
        world.update_data(owner, gear=carried)
    variant = make_variant("blade_legend", item, owner, place=place_name(world, place) if place else None)
    variant.update(legend=legend)
    record_fact(world, item, "blade_legend", owner, place=place, weight=1.5, variant=variant)
    return item


def _form_for(world, person: int | None, rng) -> str:
    form = gear.best_weapon_form(world, person) if person is not None else None
    return form or rng.choice(gear.WEAPON_FORMS)


def ensure_famous(world) -> None:
    """Seed the famous weapons of the factions and cities the world has made (once each): a faction's only once
    its master stands in the world, a city's only if a wandering master lives there (nothing is made for it)."""
    seen = set(world.get_meta("famous_keys") or [])
    added = []
    for fid in F.ensure_roster(world):
        faction = world.entity(fid)
        kind, key = faction.data.get("type"), f"faction:{fid}"
        if key in seen or faction.data.get("dissolved") or not (faction.data.get("tier") == "great" or kind in CLANS):
            continue
        leaders = staff(world, fid, ("leader",))
        if not leaders:
            continue  # the world has not made its master yet: next spring, perhaps
        added.append(key)
        rng = rng_for(world.world_seed, f"famous:{key}:keeper")
        seat = faction.data.get("seat")
        if kind in CLANS:
            keeper = None if not leaders or rng.random() < LOST_HEIRLOOM else leaders[0]
            make_famous(world, key, _form_for(world, keeper, rng), keeper, "inherited",
                        f"the heirloom of the {faction.name}" + ("" if keeper else ", lost"), seat, heirloom_of=fid)
        else:
            keeper = leaders[0] if leaders else None
            make_famous(world, key, _form_for(world, keeper, rng), keeper, "inherited",
                        f"the treasure of the {faction.name}", seat)
    for town in world.entities("town"):
        key = f"city:{town.id}"
        if town.data.get("kind") != "city" or key in seen:
            continue
        wanderers = sorted((p for p in people_at(world, town.id) if p.data.get("occupation") == "wandering swordsman"
                            and not p.data.get("is_player") and not world.targets(p.id, "wields")),
                           key=lambda p: (-realm_index(p.data.get("realm", "mortal")), p.id))
        if wanderers:  # none yet: the city is tried again next spring
            added.append(key)
            rng = rng_for(world.world_seed, f"famous:{key}:keeper")
            master = wanderers[0].id
            make_famous(world, key, _form_for(world, master, rng), master, "made", "a wandering master's own", town.id)
    if added:
        world.set_meta("famous_keys", sorted(seen | set(added)))


# --- how they pass ---------------------------------------------------------------------------------------

def heir_of(world, dead: int) -> int | None:
    return next((k for k, _ in kin_of(world, dead) if not world.entity(k).data.get("is_player")), None)


@listen("died")
def _passes_on(world, event, event_id: int) -> None:
    """At a death a famous blade goes to the killer who takes it, else the heir, else it lies there (spec 3.3)."""
    killer, dead = event.actors[0], event.actors[-1]
    owned = world.targets(dead, "owns")
    if not owned:
        return  # most of the dead own nothing: the famous list is not read
    for item in sorted(set(owned) & set(famous_weapons(world))):
        npc_killer = killer != dead and world.entity(killer) is not None \
            and not world.entity(killer).data.get("is_player") and not world.entity(killer).data.get("dead")
        if npc_killer:
            commit(world, gear.pass_events(world, dead, killer, item, event.place, "taken"))
            continue
        if killer != dead and world.entity(killer) is not None and world.entity(killer).data.get("is_player"):
            commit(world, gear.pass_events(world, dead, None, item, event.place, "lost"))  # there for the taking
            continue
        heir = heir_of(world, dead)
        commit(world, gear.pass_events(world, dead, heir, item, event.place, "inherited" if heir else "lost"))


def lying_at(world, place: int) -> list[int]:
    """The famous blades lying here, from the small index of those lying anywhere (not the whole list)."""
    return [i for i in world.get_meta("famous_lying") or [] if world.entity(i).data.get("lost_at") == place]


def take_lying_events(world, person: int, item: int, place: int) -> list[Event]:
    return gear.pass_events(world, None, person, item, place, "found")


# --- heirlooms ---------------------------------------------------------------------------------------

def return_block(world, bearer: int, item_id: int, place: int) -> str | None:
    item = world.entity(item_id)
    clan = item.data.get("heirloom_of") if item is not None else None
    if clan is None or item_id not in world.targets(bearer, "owns"):
        return "That is no clan's heirloom of yours to give."
    if world.entity(clan).data.get("seat") != place:
        return "Its clan keeps its hall elsewhere."
    if not staff(world, clan, ("leader",)):
        return "There is no clan head here to receive it."
    return None


def return_events(world, bearer: int, item_id: int, place: int) -> list[Event]:
    clan = world.entity(item_id).data["heirloom_of"]
    head = staff(world, clan, ("leader",))[0]
    return gear.pass_events(world, bearer, head, item_id, place, "given") + [
        Event("heirloom_returned", (bearer, head), place, {"item": item_id, "clan": clan},
              witnesses=(Witness(head, "grateful", 0.9, True),))]


@effect("heirloom_returned")
def _returned(world, event) -> None:
    bearer, clan = event.actors[0], event.data["clan"]
    item = world.entity(event.data["item"])
    if bearer in (item.data.get("returned_by") or []):
        return  # the clan's favour is won once
    world.update_data(item.id, returned_by=(item.data.get("returned_by") or []) + [bearer])
    import systems.founding as founding
    sect = founding.my_sect(world, bearer)
    if sect is not None:
        value = min(1.0, F.stance(world, clan, sect) + HEIRLOOM_STANCE)
        world.relate(clan, sect, "stance", value)
        world.relate(sect, clan, "stance", value)


@listen("heirloom_returned")
def _returned_news(world, event, event_id: int) -> None:
    variant = make_variant("returned_gear", event.actors[0], event.data["clan"], place=place_name(world, event.place))
    record_fact(world, event.actors[0], "returned_gear", event.data["clan"], place=event.place,
                source_event=event_id, weight=1.5, variant=variant)


# --- epithets ---------------------------------------------------------------------------------------

def _epithet(world, item, deed) -> None:
    """A famous weapon that slays someone of fame is named for it (spec 3.3), once."""
    if not item.data.get("famous") or item.data.get("epithet") or deed["kind"] != "killed" or deed.get("whom") is None:
        return
    if P.notable(world, deed["whom"]) == "leader" or P.ranked(world, deed["whom"]):
        world.update_data(item.id, epithet=f"which slew {world.entity(deed['whom']).name}")


P.DEED_HOOKS.append(_epithet)


# --- the Hundred Weapons Chronicle -------------------------------------------------------------------------

def standing_of(world, item_id: int) -> tuple:
    item = world.entity(item_id)
    return (-item.data["grade"], -round(sum(d["weight"] for d in item.data["deeds"]), 3), item_id)


def chronicle_events(world, n: int) -> list[Event]:
    from systems.rankings import ensure_pavilion
    pav = ensure_pavilion(world)
    order = sorted((i for i in famous_weapons(world) if not world.entity(i).data.get("broken")),
                   key=lambda i: standing_of(world, i))[:CHRONICLE_SIZE]
    before = world.entity(pav).data.get("weapons") or []
    return [Event("weapons_ranked", (pav,), world.entity(pav).data["town"],
                  {"year": n // 4 + 1, "order": order, "before": before})]


@effect("weapons_ranked")
def _ranked(world, event) -> None:
    world.update_data(event.actors[0], weapons=event.data["order"])


@listen("weapons_ranked")
def _ranked_news(world, event, event_id: int) -> None:
    pav, d = event.actors[0], event.data
    variant = make_variant("weapons_ranked", pav, None, place=place_name(world, event.place))
    variant.update(year=d["year"], first=(d["order"] or [None])[0])
    record_fact(world, pav, "weapons_ranked", None, place=event.place, weight=2.0, variant=variant,
                extra={"order": d["order"]})
    before = d["before"]
    for rank, item in enumerate(d["order"], 1):
        was = before.index(item) + 1 if item in before else None
        if was is None or (rank <= TOP < was):
            news = make_variant("weapon_ranked", item, None, place=place_name(world, event.place))
            news.update(rank=rank)
            record_fact(world, item, "weapon_ranked", None, place=event.place, weight=1.5, variant=news)


def season_hook(world, n: int) -> list[Event]:
    if n % 4:
        return []
    ensure_famous(world)
    return chronicle_events(world, n)


world_clock.SEASON_HOOKS.append(season_hook)


def chronicle_known(world, knower: int) -> dict | None:
    found = world.newest_known(knower, "weapons_ranked", "year")
    if found is None:
        return None
    belief, fact = found
    return {"year": belief.variant.get("year", 0), "order": fact.data.get("order", [])}
