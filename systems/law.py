"""The law (phase 3b spec 8): bounties from what a town believes, arrest, and bounty hunters."""

import systems.encounters as encounters
from systems import factions as F
from systems.attitude import is_bandit
from systems.beliefs import identities, true_identity
from systems.purse import payment_events, silver_of  # noqa: F401  (used by the engine)
from systems.realms import REALMS, realm_index
from systems.time import advance
from world.events import Event, effect
from world.gen.materialize import people_at, region_of
from world.seed import rng_for

FINE_PER, WANTED, HUNTED = 20, 30, 50
SCHEMES = frozenset({"poisoner", "spymaster", "framer", "forger", "puppet_master", "murdered",
                     "poisoned_for_hire", "enslaved"})  # 4h: 100 silver; 5c: a hired poisoning, a control pill
SCHEME_WEIGHT = 5.0
ARREST_CHANCE, HUNTER_CHANCE = 0.4, 0.2
ALLIANCE_RANGE = 3
WATCHES_PER_DAY = 4


def _alliance_doubles(world, town_id: int) -> bool:
    town = world.entity(town_id).data
    return any(world.entity(f).data["type"] == "orthodox_sect"
               and F.gap(world.entity(f).data["home"], (town["x"], town["y"])) <= ALLIANCE_RANGE
               for f in F.ensure_roster(world))


def crimes(world, town_id: int, subject: int) -> list[tuple[int, float]]:
    """The crimes this town believes of `subject`, not yet atoned: (fact id, weight x confidence)."""
    true_id = true_identity(world, subject)
    seen = identities(world, town_id, true_id) if subject == true_id else {subject}
    atoned = set(world.entity(true_id).data.get("atoned", []))
    best: dict = {}
    for belief, fact in world.known_facts(town_id):
        if belief.variant.get("actor") not in seen or fact.id in atoned:
            continue
        if fact.id not in best or belief.confidence > best[fact.id][0].confidence:
            best[fact.id] = (belief, fact)
    out = []
    doubled = None
    for belief, fact in best.values():
        target = world.entity(belief.variant.get("target")) if isinstance(belief.variant.get("target"), int) else None
        weight = 0.0
        if fact.predicate in ("killed", "robbed") and target is not None and target.kind == "person" \
                and not is_bandit(target) and not target.data.get("beast"):
            weight = fact.weight
        elif fact.predicate == "crippled":
            weight = fact.weight
        elif fact.predicate in SCHEMES:
            weight = SCHEME_WEIGHT
        elif fact.predicate == "stole" and target is not None and target.kind == "faction":
            weight = fact.weight  # a sect's armoury carried off (phase 5a)
        elif fact.predicate == "member_of" and target is not None and target.kind == "faction" \
                and target.data["type"] in F.DARK:
            doubled = _alliance_doubles(world, town_id) if doubled is None else doubled
            weight = 1.5 * (2 if doubled else 1)
        if weight:
            out.append((fact.id, weight * belief.confidence))
    return out


def bounty(world, town_id: int, subject: int) -> int:
    amount = round(FINE_PER * sum(w for _, w in crimes(world, town_id, subject)))
    from systems.lineage import inherited  # an heir answers for half the debts they inherited (phase 4b)
    entity = world.entity(subject) if isinstance(subject, int) else None
    if entity is not None and town_id not in entity.data.get("inherited_paid", []):  # until settled here
        amount += sum(round(share * bounty(world, town_id, a)) for a, share in inherited(world, town_id, subject))
    return amount if amount >= WANTED else 0


def constable_here(world, town_id: int, player: int) -> int | None:
    bureau = next((f for f in F.ensure_roster(world) if world.entity(f).data["type"] == "imperial"), None)
    members = set(F.members_of(world, bureau)) if bureau else set()
    return next((p.id for p in people_at(world, town_id, exclude=player) if p.id in members), None)


def arrest_events(world, player: int, town_id: int) -> list[Event]:
    if world.entity(player).data.get("arrest"):
        return []
    amount = bounty(world, town_id, player)
    officer = constable_here(world, town_id, player) if amount else None
    if officer is None:
        return []
    if rng_for(world.world_seed, f"arrest:{town_id}:{world.time}").random() >= ARREST_CHANCE:
        return []
    facts = [fid for fid, _ in crimes(world, town_id, player)]
    return [Event("arrest", (player, officer), town_id, {"bounty": amount, "facts": facts})]


@effect("arrest")
def _arrest(world, event) -> None:
    world.update_data(event.actors[0], arrest={"constable": event.actors[1], **event.data})


def settle_inherited(world, player: int, town: int) -> None:
    """Paying, serving or a trial settles the debts inherited in this town too (phase 4b review)."""
    paid = list(world.entity(player).data.get("inherited_paid", []))
    if town not in paid:
        world.update_data(player, inherited_paid=paid + [town])


def _atone(world, player: int, facts: list[int]) -> None:
    atoned = list(world.entity(player).data.get("atoned", []))
    world.update_data(player, atoned=atoned + [f for f in facts if f not in atoned], arrest=None)


def fine_events(world, player: int, place: int) -> list[Event]:
    a = world.entity(player).data["arrest"]
    return payment_events(player, a["constable"], place, a["bounty"], "fine") + [
        Event("fined", (player, a["constable"]), place, {"bounty": a["bounty"], "facts": a["facts"]})]


def jail_events(world, player: int, place: int) -> list[Event]:
    a = world.entity(player).data["arrest"]
    return [Event("jailed", (player, a["constable"]), place, {"days": max(1, a["bounty"] // 5), "facts": a["facts"]})]


def escape_events(world, player: int, place: int) -> list[Event]:
    a = world.entity(player).data["arrest"]
    return [Event("escaped_arrest", (player, a["constable"]), place, {})]


@effect("fined")
def _fined(world, event) -> None:
    _atone(world, event.actors[0], event.data["facts"])
    settle_inherited(world, event.actors[0], event.place)


@effect("jailed")
def _jailed(world, event) -> None:
    _atone(world, event.actors[0], event.data["facts"])
    settle_inherited(world, event.actors[0], event.place)
    advance(world, event.data["days"] * WATCHES_PER_DAY)


@effect("escaped_arrest")
def _escaped(world, event) -> None:
    world.update_data(event.actors[0], arrest=None)


def bounty_hunter_encounter(world, player: int, town, rng):
    """With a price of HUNTED or more on the player here, a hunter may be waiting on the road."""
    if bounty(world, town.id, player) < HUNTED:
        return None
    if rng_for(world.world_seed, f"bounty:{player}:{world.time}").random() >= HUNTER_CHANCE:
        return None
    region = region_of(world, town.id)
    slot = encounters._free_roamer_slot(world, region)
    danger = encounters.region_danger(world.world_seed, region.data["x"], region.data["y"])
    hunter = encounters.make_roamer(world, region, "wanderer", slot, danger)
    stronger = min(len(REALMS) - 1, realm_index(world.entity(player).data.get("realm", "mortal")) + 1)
    world.update_data(hunter, realm=REALMS[stronger].label, occupation="bounty hunter")
    return encounters.encounter_events(player, hunter, town.id, "bounty_hunter", 0)


encounters.ROAD_HOOKS.append(bounty_hunter_encounter)
