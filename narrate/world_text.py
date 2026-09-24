"""What the player is told about the living world (phase 4a spec 7)."""

from narrate.gossip_text import EXTRA_PHRASES, rumour_text
from narrate.outcomes import outcome, summary

NEWS_KINDS = frozenset({"died", "killed", "broke_through", "married", "born", "moved", "apprenticed",
                        "clashed_with", "lost_hall", "promoted", "faction_destroyed", "faction_founded"})
COUNTS = {1: "one child", 2: "two children", 3: "three children"}

WORLD_PHRASES = {
    "died": "{actor} died.",
    "broke_through": "{actor} broke through to a higher realm.",
    "married": "{actor} married {target}.",
    "born": "{actor} had a child, {target}.",
    "moved": "{actor} moved to {target}.",
    "apprenticed": "{actor} took {target} as a disciple.",
    "sworn_siblings": "{actor} swore an oath of kinship with {target}.",
    "clashed_with": "The {actor} beat the {target} in a clash.",
    "lost_hall": "The {actor} lost a hall to the {target}.",
    "faction_destroyed": "The {actor} was destroyed.",
    "faction_founded": "The {actor} was founded.",
}
EXTRA_PHRASES.update(WORLD_PHRASES)


def life_facts(world, person) -> list[str]:
    """One brief line of a person's age and family (spec §7.2), without naming anyone the player may not know."""
    import systems.agendas as agendas
    age = person.data.get("age")
    if age is None or person.kind != "person":
        return []
    parts = [f"{person.name} is {int(age)} years old"]
    if agendas.spouse_of(world, person.id) is not None:
        parts.append("married")
    children = len(agendas.children_of(world, person.id))
    if children:
        parts.append(f"with {COUNTS.get(children, f'{children} children')}")
    return [", ".join(parts) + "."]


def town_news(world, town: int, player: int) -> str | None:
    """The newest change at this town that the player believes, as they would tell it."""
    news = [(b, f) for b, f in world.known_facts(player) if f.place == town and f.predicate in NEWS_KINDS]
    if not news:
        return None
    belief, _ = max(news, key=lambda p: (p[1].time, p[1].id))
    return rumour_text(world, belief.variant, player)


@outcome("heard_death", body_facts=False)
def _heard_death(world, event):
    return [f"You hear that {world.entity(event.actors[1]).name} has died."], {}


@summary("heard_death")
def _heard_death_line(world, entry, names, place, other):
    return f"Heard: {other} died."
