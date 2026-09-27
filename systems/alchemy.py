"""Recipes, experiments and refining (phase 5b spec 3).

Herbs in the furnace sum to four properties: a dominant element, a polarity, a total potency and a total
toxicity. A base recipe (`systems/data/recipes.toml`) asks one of each; the herbs that meet all four discover it,
three of four leave a hint, fewer a sludge. A known recipe is refined with one roll on mastery, comprehension and
the alchemy level; each success raises both.
"""

import math
import tomllib
from pathlib import Path

import systems.herbs as H
import systems.toxins as toxins
from systems.bodies import load_body, save_body
from systems.purse import silver_of
from systems.time import advance
from world.body import add_injury
from world.events import Event, effect
from world.seed import rng_for

RECIPES = tomllib.loads((Path(__file__).parent / "data" / "recipes.toml").read_text(encoding="utf-8"))
NEEDS = ("element", "polarity", "potency", "toxicity")
MIN_HERBS, MAX_HERBS = 2, 4
BALANCED = 1               # a net polarity within this is balanced
FUMES_AT = 5               # a sludge this toxic poisons its maker
DISCOVERED_MASTERY, MASTERY_STEP = 0.1, 0.05
CHANCE_BOUNDS = (0.1, 0.95)
CRACK_SHARE = 0.1          # the worst tenth of the chance's failing rolls cracks the furnace (ruling 6)
WATCHES = 2
FIRST_WORDS = ("Azure", "Jade", "Golden", "Crimson", "Nine-Turn", "Heavenly", "Purple Cloud", "Silver Moon",
               "Black Tortoise", "White Crane", "Thousand-Year", "Spring Rain")
LAST_WORDS = {"qi": "Qi Pill", "bottleneck": "Breakthrough Pill", "purity": "Clear Marrow Pill",
              "healing": "Wound-Closing Pill", "mending": "Meridian-Mending Pill", "calming": "Heart-Calming Pill",
              "cleansing": "Cleansing Pill", "antidote": "Antidote", "poison": "Poison", "venom": "Blade Venom",
              "tempering": "Tempering Draught"}
HINTS = {"element": "the herbs lean to the wrong element", "polarity": "the balance of yin and yang is off",
         "potency": "the brew is too weak", "toxicity": "the brew is too toxic" }


# --- what herbs add up to -------------------------------------------------------------------------------------

def combine(names: list[str]) -> dict:
    """The four properties of these herbs together."""
    weights: dict[str, int] = {}
    net = 0
    for name in names:
        p = H.props(name)
        weights[p["element"]] = weights.get(p["element"], 0) + p["potency"]
        net += {"yang": 1, "yin": -1}.get(p["polarity"], 0) * p["potency"]
    element = max(sorted(weights), key=lambda e: weights[e])
    polarity = "balanced" if abs(net) <= BALANCED else ("yang" if net > 0 else "yin")
    return {"element": element, "polarity": polarity, "potency": sum(H.props(n)["potency"] for n in names),
            "toxicity": sum(H.props(n)["toxicity"] for n in names)}


def met(recipe: dict, mix: dict) -> dict[str, bool]:
    toxic = mix["toxicity"] >= recipe["toxic"] if "toxic" in recipe else mix["toxicity"] <= recipe["toxicity"]
    return {"element": mix["element"] == recipe["element"], "polarity": mix["polarity"] == recipe["polarity"],
            "potency": mix["potency"] >= recipe["potency"], "toxicity": toxic}


def best_match(mix: dict) -> tuple[str | None, dict]:
    """The base recipe these herbs come closest to, and which needs they meet."""
    scored = sorted(((sum(met(r, mix).values()), key) for key, r in RECIPES.items()), key=lambda s: (-s[0], s[1]))
    score, key = scored[0]
    return key, met(RECIPES[key], mix)


# --- recipes as knowledge ----------------------------------------------------------------------------------

def recipe_entity(world, key: str) -> int:
    """A world's recipe for this base: named once, the same entity for everyone who learns it."""
    path = f"recipe:{key}"
    found = world.entity_by_seed(path)
    if found is not None:
        return found.id
    rng = rng_for(world.world_seed, path)
    base = RECIPES[key]
    name = f"{rng.choice(FIRST_WORDS)} {LAST_WORDS[base['effect']]}"
    return world.add_entity("recipe", name, {"key": key, **base}, path)


def known_recipes(world, person: int) -> list[tuple[int, float]]:
    return [(r, value) for r, value, _ in world.relations_from(person, "knows_recipe")]


def mastery(world, person: int, recipe: int) -> float | None:
    return next((v for r, v in known_recipes(world, person) if r == recipe), None)


def level(world, person: int) -> int:
    return int(math.floor(math.sqrt(world.entity(person).data.get("alchemy_xp", 0) / 10)))


# --- the furnace -------------------------------------------------------------------------------------------

def furnace_block(world, person: int, place) -> str | None:
    """One's own furnace, or an apothecary's to rent in a town."""
    if H.furnace_of(world, person) is not None:
        return None
    if world.entity(place).kind != "town":
        return "You need a furnace, or a town's apothecary to rent one."
    if silver_of(world, person) < H.FURNACE_RENT:
        return f"The apothecary's furnace costs {H.FURNACE_RENT} silver."
    return None


def _rent(world, person: int) -> int:
    return 0 if H.furnace_of(world, person) is not None else H.FURNACE_RENT


def _herbs_block(world, person: int, herb_ids) -> str | None:
    if not MIN_HERBS <= len(herb_ids) <= MAX_HERBS or len(set(herb_ids)) != len(herb_ids):
        return f"Put {MIN_HERBS} to {MAX_HERBS} herbs in the furnace."
    owned = set(world.targets(person, "owns"))
    if any(h not in owned or H.herb_info(world.entity(h)) is None for h in herb_ids):
        return "You have no such herbs."
    return None


# --- experimenting (spec 3.2) ---------------------------------------------------------------------------------

def experiment_block(world, person: int, place, herb_ids) -> str | None:
    return _herbs_block(world, person, herb_ids) or furnace_block(world, person, place)


def experiment_events(world, person: int, place, herb_ids) -> list[Event]:
    names = [H.herb_info(world.entity(h))[0] for h in herb_ids]
    mix = combine(names)
    key, needs = best_match(mix)
    score = sum(needs.values())
    grade = min(H.herb_info(world.entity(h))[1] for h in herb_ids) + 1
    result = "discovered" if score == len(NEEDS) else "hint" if score == len(NEEDS) - 1 else "sludge"
    missed = next((n for n in NEEDS if not needs[n]), None) if result == "hint" else None
    return [Event("experimented", (person,), place, {
        "herbs": list(herb_ids), "names": names, "mix": mix, "result": result,
        "recipe": key if result != "sludge" else None, "missed": missed, "grade": grade,
        "rent": _rent(world, person), "fumes": result == "sludge" and mix["toxicity"] >= FUMES_AT})]


@effect("experimented")
def _experimented(world, event) -> None:
    person, d = event.actors[0], event.data
    world.update_data(person, silver=silver_of(world, person) - d["rent"])
    H.spend(world, person, d["herbs"])
    advance(world, WATCHES)
    if d["result"] == "discovered":
        H.learn(world, person, d["names"])  # only a success teaches its herbs (spec 2.2)
        recipe = recipe_entity(world, d["recipe"])
        if mastery(world, person, recipe) is None:
            world.relate(person, recipe, "knows_recipe", DISCOVERED_MASTERY)
        make_pill(world, person, recipe, d["grade"], 0.4 + 0.5 * DISCOVERED_MASTERY)
    elif d["result"] == "hint":
        hints = list(world.entity(person).data.get("alchemy_hints") or [])
        hint = f"{' + '.join(d['names'])}: {HINTS[d['missed']]}"
        if hint not in hints:
            world.update_data(person, alchemy_hints=(hints + [hint])[-20:])
    elif d["fumes"]:
        toxins.poison(world, person, min(5, d["mix"]["toxicity"] // 2), d["mix"]["toxicity"], "a furnace's fumes")


# --- refining (spec 3.3) --------------------------------------------------------------------------------------

def refine_chance(world, person: int, recipe: int) -> float:
    body = load_body(world, person)
    wit = body.physique.get("comprehension", 5)
    raw = 0.35 + 0.4 * (mastery(world, person, recipe) or 0.0) + 0.03 * (wit - 5) + 0.05 * level(world, person)
    return max(CHANCE_BOUNDS[0], min(CHANCE_BOUNDS[1], raw))


def refine_block(world, person: int, place, recipe: int, herb_ids) -> str | None:
    if mastery(world, person, recipe) is None:
        return "You do not know that recipe."
    why = _herbs_block(world, person, herb_ids) or furnace_block(world, person, place)
    if why:
        return why
    needs = met(RECIPES[world.entity(recipe).data["key"]], combine([H.herb_info(world.entity(h))[0] for h in herb_ids]))
    if not all(needs.values()):
        return f"These herbs will not make it: {HINTS[next(n for n in NEEDS if not needs[n])]}."
    return None


def refine_events(world, person: int, place, recipe: int, herb_ids) -> list[Event]:
    base = world.entity(recipe).data
    mix = combine([H.herb_info(world.entity(h))[0] for h in herb_ids])
    skill = mastery(world, person, recipe)
    chance = refine_chance(world, person, recipe)
    roll = rng_for(world.world_seed, f"refine:{person}:{recipe}:{world.time}").random()
    success = roll < chance
    grade = min(5, min(H.herb_info(world.entity(h))[1] for h in herb_ids) + 1 + (1 if skill >= 0.8 else 0))
    allowance = base.get("toxicity", mix["toxicity"])
    purity = max(0.0, min(1.0, round(0.4 + 0.5 * skill - 0.1 * max(0, mix["toxicity"] - allowance), 3)))
    count = 1 + min(2, max(0, (mix["potency"] - base["potency"]) // 3))
    return [Event("refined", (person,), place, {
        "recipe": recipe, "herbs": list(herb_ids), "names": [H.herb_info(world.entity(h))[0] for h in herb_ids],
        "success": success, "count": count if success else 0, "grade": grade, "purity": purity,
        "cracked": not success and roll > 1 - chance * CRACK_SHARE, "rent": _rent(world, person)})]


@effect("refined")
def _refined(world, event) -> None:
    person, d = event.actors[0], event.data
    world.update_data(person, silver=silver_of(world, person) - d["rent"])
    H.spend(world, person, d["herbs"])
    advance(world, WATCHES)
    if d["success"]:
        H.learn(world, person, d["names"])
        for _ in range(d["count"]):
            make_pill(world, person, d["recipe"], d["grade"], d["purity"])
        skill = mastery(world, person, d["recipe"])
        world.relate(person, d["recipe"], "knows_recipe", round(min(1.0, skill + MASTERY_STEP), 3))
        world.update_data(person, alchemy_xp=world.entity(person).data.get("alchemy_xp", 0) + d["grade"])
    elif d["cracked"]:
        furnace = H.furnace_of(world, person)
        if furnace is not None:
            world.update_data(furnace, cracked=True)
        body = load_body(world, person)
        add_injury(body, "right arm", "bruise", 2, world.time, "a cracked furnace")
        save_body(world, person, body)


# --- pills ---------------------------------------------------------------------------------------------------

def make_pill(world, person: int, recipe: int, grade: int, purity: float) -> int:
    """A pill of this recipe (spec 4.1), carried by its maker."""
    base = world.entity(recipe)
    item = world.add_entity("pill", base.name, {"effect": base.data["effect"], "grade": int(grade),
                                                "purity": round(float(purity), 3), "recipe": recipe, "maker": person,
                                                "used": False})
    world.relate(person, item, "owns")
    return item


def find_batch(world, person: int, recipe: int) -> list[int] | None:
    """The cheapest handful of carried herbs that meets a known recipe, if any (for the refine choice)."""
    from itertools import combinations
    base = RECIPES[world.entity(recipe).data["key"]]
    herbs = sorted(H.herbs_of(world, person), key=lambda h: (H.herb_info(h)[1], H.props(H.herb_info(h)[0])["price"], h.id))
    fitting = [h for h in herbs if H.props(H.herb_info(h)[0])["element"] in (base["element"], "none")
               or H.props(H.herb_info(h)[0])["polarity"] == base["polarity"]][:10]
    for size in range(MIN_HERBS, MAX_HERBS + 1):
        for batch in combinations(fitting, size):
            if all(met(base, combine([H.herb_info(h)[0] for h in batch])).values()):
                return [h.id for h in batch]
    return None
