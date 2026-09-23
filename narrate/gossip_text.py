"""What the player is told about rumours: built from a story variant, never from the fact behind it."""

from narrate.outcomes import cap, outcome, summary
from systems.beliefs import confidence_phrase
from systems.realms import REALMS, realm_index

VERBS = {
    "killed": "killed", "crippled": "crippled", "robbed": "robbed", "spared": "spared", "defeated": "defeated",
    "fled_from": "fled from", "left_for_dead": "left", "paid_off": "paid off", "lied_about": "spread lies about",
}
COUNT_WORDS = {2: "one other", 3: "two others"}
REALM_DEEDS = frozenset({"defeated", "killed", "crippled", "robbed", "spared", "left_for_dead"})
# Later systems add their own story shapes here: {actor}, {target} and {be} ("are" for you, else "is").
EXTRA_PHRASES = {"member_of": "{actor} {be} of the {target}."}


def who(world, entity_id, viewer: int) -> str:
    if entity_id is None:
        return "a masked fighter"
    if entity_id == viewer:
        return "you"
    entity = world.entity(entity_id)
    return entity.name if entity else "someone"


def rumour_text(world, variant: dict, viewer: int) -> str:
    """One plain sentence for a story, as this viewer would hear it."""
    actor = who(world, variant.get("actor"), viewer)
    predicate = variant.get("predicate")
    target = who(world, variant["target"], viewer) if variant.get("target") is not None else None
    if predicate == "is":
        return cap(f"{actor} is really {target}.")
    if predicate in EXTRA_PHRASES:
        be = "are" if actor == "you" else "is"
        return cap(EXTRA_PHRASES[predicate].format(actor=actor, target=target or "someone", be=be))
    if predicate == "owns_manual":
        has = "have" if actor == "you" else "has"
        return cap(f"{actor} {has} the {variant['art']}.") if variant.get("art") else cap(f"{actor} {has} a secret manual.")
    verb = "nearly killed" if predicate == "killed" and variant.get("soft") else VERBS.get(predicate, predicate)
    whom = target or "someone"
    if variant.get("count", 1) > 1:
        whom += f" and {COUNT_WORDS.get(variant['count'], 'others')}"
    text = f"{actor} {verb} {whom}"
    if predicate == "left_for_dead":
        text += " for dead"
    realm = variant.get("realm")
    if realm and realm_index(realm) > 0 and predicate in REALM_DEEDS:
        text += f" (a {REALMS[realm_index(realm)].name} fighter)"
    if variant.get("art") and predicate != "owns_manual":
        text += f" with the {variant['art']}"
    if variant.get("place"):
        text += f" in {variant['place']}"
    return cap(text + ".")


@outcome("heard", body_facts=False)
def _heard(world, event):
    d = event.data
    teller = world.entity(event.actors[1]).name
    text = rumour_text(world, d["variant"], event.actors[0])
    return [f"{cap(teller)} tells you: {text} ({confidence_phrase(d['hops'], d['confidence'])})"], {}


@outcome("no_news", body_facts=False)
def _no_news(world, event):
    about = event.data.get("about")
    if about is None:
        return ["They have heard nothing new."], {}
    if about == world.entity(event.actors[0]).name:
        return ["They have never heard of you."], {}
    return [f"They have never heard of {about}."], {}


@outcome("told", body_facts=False)
def _told(world, event):
    name = cap(world.entity(event.actors[1]).name)
    return ([f"{name} takes it in and nods."] if event.data["accepted"] else [f"{name} doesn't believe you."]), {}


@outcome("lie_exposed", body_facts=False)
def _exposed(world, event):
    return [f"{cap(world.entity(event.actors[1]).name)} has learned that you lied about them."], {}


@summary("heard")
def _heard_line(world, entry, names, place, other):
    return f"Heard news from {other}."


@summary("no_news")
def _no_news_line(world, entry, names, place, other):
    return f"{cap(other)} had no news for you."


@summary("told")
def _told_line(world, entry, names, place, other):
    return f"Spread a lie to {other}." if entry.data.get("invented") else f"Told {other} a rumour."


@summary("lie_exposed")
def _exposed_line(world, entry, names, place, other):
    return f"{cap(other)} found out you lied about them."
