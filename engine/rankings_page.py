"""The rankings page (F10, phase 4d spec 7.2): the Pavilion's lists, as far as you have seen them."""

from narrate.base import Line
from systems import rankings as R

LABELS = (("heaven", "Heaven"), ("earth", "Earth"), ("human", "Men"), ("young", "Young Dragons"))


def _dead_you_know_of(world, player: int) -> set[int]:
    dead = set()
    for belief, fact in world.known_facts(player):
        if fact.predicate == "died":
            dead.add(fact.subject)
        elif fact.predicate == "killed" and belief.variant.get("target") is not None:
            dead.add(belief.variant["target"])
    return dead


def rankings_lines(world, player: int) -> list[Line]:
    lines: list[Line] = [("The Heavenly Ranking Pavilion", "heading")]
    known = R.latest(world, player)
    if known is None:
        return lines + [("  You have not seen the Pavilion's lists. Every city posts them each spring.", "dim")]
    lines.append((f"  Your copy: the lists of year {known['year']}, {max(0, (world.time - known['time']) // 4)} days old.", "dim"))
    mine = R.rank_of_you(world, known["lists"], player)
    if mine:
        lines.append((f"  You are {R.title(*mine)}.", "dim"))
    dead = _dead_you_know_of(world, player)
    masks = {p.id: p.name for p in world.entities("persona") if p.data.get("of") == player}
    for name, label in LABELS:
        names = known["lists"].get(name, [])
        if not names:
            continue
        lines.append((f"{label}:", "heading"))
        for place, person in enumerate(names, 1):
            who = "you" if person == player else f"you, as {masks[person]}" if person in masks \
                else world.entity(person).name
            lines.append((f"  {place:>2}. {who}{' (dead, you have heard)' if person in dead else ''}", "dim"))
    return lines
