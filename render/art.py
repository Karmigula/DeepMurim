"""ASCII art: parse `.art` files and compose layered scenes and portraits.

No pygame here. Cells carry palette keys; the layout resolves them to colours.
"""

import re
from functools import cache

from paths import bundled

ArtCell = tuple[str, str] | None
Art = list[list[ArtCell]]
MARKUP = re.compile(r"\{(/|[a-z_]+)\}")


def parse_art(text: str) -> Art:
    rows: Art = []
    colour = "default"
    for raw in text.splitlines():
        if raw.startswith(";"):
            continue
        row: list[ArtCell] = []
        pos = 0
        for match in MARKUP.finditer(raw):
            row += [None if ch == " " else (ch, colour) for ch in raw[pos:match.start()]]
            colour = "default" if match.group(1) == "/" else match.group(1)
            pos = match.end()
        row += [None if ch == " " else (ch, colour) for ch in raw[pos:]]
        rows.append(row)
    return rows


@cache
def _load(name: str) -> tuple[tuple[ArtCell, ...], ...]:
    path = bundled("assets", "art", f"{name}.art")
    if not path.is_file():
        return ()
    return tuple(tuple(row) for row in parse_art(path.read_text(encoding="utf-8")))


def load_art(name: str) -> Art:
    return [list(row) for row in _load(name)]


def art_width(art: Art) -> int:
    return max((len(row) for row in art), default=0)


def blank(w: int, h: int) -> Art:
    return [[None] * w for _ in range(h)]


def stamp(canvas: Art, art: Art, top: int, left: int) -> None:
    """Draw `art` onto `canvas`; transparent cells and anything off-canvas are skipped."""
    height = len(canvas)
    width = len(canvas[0]) if canvas else 0
    for r, row in enumerate(art):
        y = top + r
        if not 0 <= y < height:
            continue
        for c, cell in enumerate(row):
            x = left + c
            if cell is not None and 0 <= x < width:
                canvas[y][x] = cell


def compose_scene(terrain: str, settlement: str, watch: int, w: int, h: int) -> Art:
    canvas = blank(w, h)
    sky = load_art(f"sky_{watch}")
    stamp(canvas, sky, 0, (w - art_width(sky)) // 2)
    for layer in (load_art(f"terrain_{terrain}"), load_art(f"settlement_{settlement}")):
        stamp(canvas, layer, h - len(layer), (w - art_width(layer)) // 2)
    return canvas


def compose_portrait(parts: dict, w: int, h: int) -> Art:
    pieces = [load_art(f"{part}_{parts.get(part, 0)}") for part in ("hair", "face", "robe")]
    canvas = blank(w, h)
    top = max(0, (h - sum(len(p) for p in pieces)) // 2)
    for piece in pieces:
        stamp(canvas, piece, top, (w - art_width(piece)) // 2)
        top += len(piece)
    return canvas


def render_request(request: dict, w: int, h: int) -> Art:
    kind = request.get("type")
    if kind == "scene":
        return compose_scene(request["terrain"], request["settlement"], request["watch"], w, h)
    if kind == "portrait":
        return compose_portrait(request["parts"], w, h)
    return blank(w, h)
