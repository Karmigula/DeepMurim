"""The player's gear on screen (phase 5a spec 5-6): the inventory, an item's page, the sheet's line, the Chronicle.

Knowledge vs truth: an item's page names only the owners the player has met or heard of, and only the deeds they
did themselves or believe a tale of; the maker only if they bought or drew it, or believe a tale naming the maker.
"""

import systems.famous as FW
import systems.gear as gear
from systems.beliefs import known_people
from systems.provenance import LEGENDS

HOW_WORDS = {"carried": "carried by", "bought": "bought by", "taken": "taken by", "drawn": "drawn by",
             "inherited": "inherited by", "won": "won by", "given": "given to", "found": "found by",
             "made": "made for", "sold": "sold by", "returned": "returned by", "lost": "lost by"}


def _label(item) -> str:
    grade = gear.GRADES[item.data["grade"]]
    extra = ", famous" if item.data.get("famous") else ""
    extra += ", broken" if item.data.get("broken") else ""
    extra += ", the sect's" if item.data.get("armoury") is not None else ""
    return f"{item.name} ({grade}{extra})"


def history_line(world, viewer: int, item) -> str:
    known = set(known_people(world, viewer)) | {viewer}
    steps = []
    for step in item.data["owners"][-3:]:
        who = "you" if step["person"] == viewer else world.entity(step["person"]).name \
            if step["person"] in known else "someone"
        steps.append(f"{HOW_WORDS.get(step['how'], step['how'])} {who}")
    return "; ".join(steps) or "no history you know"


def inventory_lines(world, player: int) -> list:
    lines = [("Your gear", "heading")]
    weapon, armour = gear.item_in(world, player, "weapon"), gear.item_in(world, player, "armour")
    held = gear.weapon_of(world, player)
    if weapon is not None:
        lines.append((f"  Wielding: {_label(weapon)} - {history_line(world, player, weapon)}", "dim"))
    elif held is not None:
        lines.append((f"  Wielding: {gear.gear_name('weapon', held['form'] or 'blade', held['grade'])} "
                      f"({gear.GRADES[held['grade']]}), plain and unremarked", "dim"))
    else:
        lines.append(("  Wielding: nothing", "dim"))
    worn = gear.armour_of(world, player)
    if armour is not None:
        lines.append((f"  Wearing: {_label(armour)}", "dim"))
    elif worn is not None:
        lines.append((f"  Wearing: plain armour ({gear.GRADES[worn['grade']]})", "dim"))
    else:
        lines.append(("  Wearing: cloth", "dim"))
    others = [i for i in gear.gear_items(world, player) if i.id not in {getattr(weapon, "id", None), getattr(armour, "id", None)}]
    for item in others:
        lines.append((f"  {_label(item)} - {history_line(world, player, item)}", "dim"))
    return lines


def known_deeds(world, viewer: int, item) -> list[dict]:
    told = {fact.source_event for _, fact in world.known_facts_about([viewer], actors=[item.id])
            if fact.predicate in LEGENDS}
    mine = {e.id for e in world.chronicle_about(viewer, limit=200)}
    return [d for d in item.data["deeds"] if d["event"] in told or d["event"] in mine]


def legends_known(world, viewer: int, item) -> list[str]:
    from narrate.gossip_text import rumour_text  # the narration loads after the engine's pages
    return [rumour_text(world, belief.variant, viewer)
            for belief, fact in world.known_facts_about([viewer], actors=[item.id]) if fact.predicate in LEGENDS]


def item_lines(world, viewer: int, item) -> list:
    d = item.data
    what = d["form"] if d["slot"] == "weapon" else gear.ARMOUR_WORDS[d["form"]]
    told = legends_known(world, viewer, item)
    epithet = d.get("epithet") if told else None  # the name its tales give it, for one who has heard them
    lines = [(item.name + (f", {epithet}" if epithet else ""), "heading"),
             (f"  {'An' if d['grade'] == 0 else 'A'} {gear.GRADES[d['grade']]} {what}" + (" (broken)" if d.get("broken") else ""), "dim")]
    mine = any(s["person"] == viewer and s["how"] in ("bought", "drawn", "made") for s in d["owners"])
    maker = d.get("maker")
    if maker is not None and mine:
        name = maker if isinstance(maker, str) else world.entity(maker).name
        lines.append((f"  Made by {name}", "dim"))
    lines.append((f"  Its hands: {history_line(world, viewer, item)}", "dim"))
    known = set(known_people(world, viewer)) | {viewer}
    for deed in known_deeds(world, viewer, item):
        whom = deed.get("whom")
        name = "you" if whom == viewer else world.entity(whom).name if whom in known else "someone" if whom else ""
        lines.append((f"  It {({'killed': 'slew', 'bested': 'bested', 'won_tournament': 'won a tournament'})[deed['kind']]}"
                      f"{' ' + name if name else ''}.", "dim"))
    for tale in told[:3]:
        lines.append((f"  Known as: {tale}", "dim"))
    return lines


def weapon_words(world, player: int, form: str) -> str:
    """The sheet's note on an art: what the weapon in hand does for it (spec 5); hand arts need none."""
    if form not in gear.WEAPON_FORMS:
        return ""
    item = gear.item_in(world, player, "weapon")
    held = gear.weapon_of(world, player)
    name = item.name if item is not None else ("a plain weapon" if held else "bare hands")
    return f" | {name} x{gear.weapon_mult(world, player, form):.2f}"


def armour_words(world, player: int) -> str:
    share = gear.armour_share(world, player)
    return f"armour takes {share:.0%} off a wound" if share else "no armour"


def chronicle_lines(world, player: int) -> list:
    known = FW.chronicle_known(world, player)
    if known is None:
        return []
    lines = [("", "default"), (f"The Hundred Weapons Chronicle (year {known['year']})", "heading")]
    for rank, item_id in enumerate(known["order"][:10], 1):
        item = world.entity(item_id)
        if item is not None:
            lines.append((f"  {rank}. {item.name} ({gear.GRADES[item.data['grade']]})", "dim"))
    return lines
