"""The state pack (phase 6 spec 4): what the player knows of themselves and their surroundings, for every call.

Built from the pages the player can already read (the sheet, the scene's presence line, the journal), so it shows
nothing they could not see: no ids, no hidden truths, no one they have not heard of. Plain text, bounded in size.
"""

from engine.alchemy_page import poison_words
from engine.journal import summarize
from engine.sheet import sheet_lines
from narrate.brief import _place
from systems.bodies import load_body

MAX_PACK = 2500
MAX_CARRIED = 12
LATELY = 6
QUIET = frozenset({"exchange", "player_aged", "delve_moved", "delve_rested"})
SKIPPED = ("Meridians:", "Lung ", "Governing ")  # the sheet's meridian chart says nothing a writer can use
LIMITS = (
    "a mortal: no qi to speak of; cannot leap rooftops, walk on water or stand against a trained fighter",
    "third-rate: a little qi; can best mortals and leap a wall, not a master",
    "second-rate: real qi; can run along a roof, still no match for a first-rate master",
    "first-rate: a master of the martial world; still cannot fly or face a peak master",
    "peak: among the strongest of the land; the transcendent are beyond you",
    "transcendent: few in the land can stand against you",
    "profound: a legend; only a handful are your equal",
    "life-and-death: at the summit of the martial world",
)


def _sheet(world, player: int) -> list[str]:
    out = []
    for text, key in sheet_lines(world, player):
        text = text.strip()
        if not text or key == "heading" or text == "none" or text.startswith(SKIPPED) or "●" in text or "·" in text:
            continue
        out.append(text)
    return out


def _carried(world, player: int) -> str:
    names = sorted(world.entity(i).name for i in world.targets(player, "owns")
                   if world.entity(i) is not None and not world.entity(i).data.get("used"))
    if not names:
        return "nothing of note"
    shown = ", ".join(names[:MAX_CARRIED])
    return shown + (f", and {len(names) - MAX_CARRIED} more" if len(names) > MAX_CARRIED else "")


def _lately(world, player: int) -> list[str]:
    entries = [e for e in reversed(world.chronicle_about(player, limit=60)) if e.kind not in QUIET]
    return [summarize(world, e) for e in entries[-LATELY:]]


def build_pack(game) -> str:
    """The pack for this moment of this game (the player's view, never the world's truth)."""
    world, me = game.world, game.player.id
    place = _place(world, game.place.id)
    body = load_body(world, me)
    silver = int(world.entity(me).data.get("silver", 0))
    sections = [  # the sheet last: if the pack must be cut, it is the sheet that loses its tail
        ("HERE", [f"{place.name} ({place.kind}) in {place.region}; {place.terrain}; {place.season}, {place.watch}"]
         + [text for text, _ in game._presence()]),
        ("LIMITS", [LIMITS[min(body.realm, len(LIMITS) - 1)], f"you carry {silver} silver"]),
        ("CARRYING", [_carried(world, me)]),
        ("LATELY", _lately(world, me) or ["nothing yet"]),
        ("YOU", [f"{game.player.name}, age {int(game.player.data.get('age', 18))}"] + poison_words(body)
         + _sheet(world, me)),
    ]
    text = "\n".join(f"{name}:\n" + "\n".join(f"- {line}" for line in lines) for name, lines in sections)
    return text if len(text) <= MAX_PACK else text[:MAX_PACK - 1] + "…"
