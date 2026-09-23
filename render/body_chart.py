"""An ASCII figure coloured by injuries, plus meridian states. Pure: no pygame.

Parts: H head, T torso, R right arm, L left arm, r right leg, l left leg. The
figure faces the viewer, so its right side is on the viewer's left.
"""

from render.art import Art, blank, stamp
from world.body import EXTRAORDINARY, REGULAR, unhealed

FIGURE = (
    "    .-.    ",
    "   (   )   ",
    "    '-'    ",
    "  __| |__  ",
    " /  | |  \\ ",
    "/   | |   \\",
    "    |_|    ",
    "    / \\    ",
    "   /   \\   ",
    "  /     \\  ",
    " /       \\ ",
)
MASK = (
    "    HHH    ",
    "   HHHHH   ",
    "    HHH    ",
    "  RRTTTLL  ",
    " R  TTT  L ",
    "R   TTT   L",
    "    TTT    ",
    "    r l    ",
    "   r   l   ",
    "  r     l  ",
    " r       l ",
)
PART = {"H": "head", "T": "torso", "R": "right arm", "L": "left arm", "r": "right leg", "l": "left leg"}
SYMBOL = {"open": "●", "damaged": "◐", "scarred": "◌", "severed": "×", "blocked": "·"}
STATE_COLOUR = {"open": "green", "damaged": "gold", "scarred": "brown", "severed": "red", "blocked": "dim"}
SHORT = {
    "Governing": "Gov", "Conception": "Con", "Penetrating": "Pen", "Girdle": "Gir",
    "Yin Linking": "YinL", "Yang Linking": "YangL", "Yin Heel": "YinH", "Yang Heel": "YangH",
}


def part_colour(body, part: str, now: int) -> str:
    hurt = [i for i in unhealed(body, now) if i.location == part]
    if any(i.permanent for i in hurt):
        return "purple"
    worst = max((i.severity for i in hurt), default=0)
    return "green" if worst == 0 else "gold" if worst <= 2 else "red"


def _segment(text: str, key: str) -> list:
    return [None if ch == " " else (ch, key) for ch in text]


def body_chart(body, now: int, width: int, height: int) -> Art:
    rows: Art = []
    for text, mask in zip(FIGURE, MASK):
        rows.append([None if ch == " " else (ch, part_colour(body, PART[m], now)) for ch, m in zip(text, mask)])
    rows.append([])
    for group in (EXTRAORDINARY[:4], EXTRAORDINARY[4:]):
        row: list = []
        for name in group:
            state = body.meridians[name].state
            row += _segment(f"{SHORT[name]}{SYMBOL[state]} ", STATE_COLOUR[state])
        rows.append(row)
    summary: list = _segment("Regular ", "dim")
    for state in ("open", "damaged", "scarred", "severed"):
        count = sum(1 for m in REGULAR if body.meridians[m].state == state)
        if count:
            summary += _segment(f"{count}{SYMBOL[state]} ", STATE_COLOUR[state])
    rows.append(summary)
    canvas = blank(width, height)
    top = max(0, (height - len(rows)) // 2)
    for r, row in enumerate(rows):
        stamp(canvas, [row], top + r, (width - len(row)) // 2)
    return canvas
