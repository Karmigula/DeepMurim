"""Title, name-entry and creation screens as grids. No pygame."""

from config import Color
from render.art import art_width, load_art
from render.layout import Grid, _Canvas


def compose_title(
    cols: int, rows: int, palette: dict[str, Color], options: list[str], selected: int,
    message: str = "", prompt: str | None = None, message_key: str = "red",
) -> Grid:
    canvas = _Canvas(cols, rows, palette)
    title = load_art("title")
    lines = len(title) + 2 + (1 if prompt else len(options)) + (2 if message else 0)
    top = max(0, (rows - lines) // 2)
    left = max(0, (cols - art_width(title)) // 2)
    for r, row in enumerate(title):
        for c, cell in enumerate(row):
            if cell is not None:
                canvas.put(top + r, left + c, cell[0], cell[1])
    y = top + len(title) + 2
    if prompt is not None:
        canvas.put(y, max(0, (cols - len(prompt)) // 2), prompt, "player")
        y += 1
    else:
        width = max((len(o) for o in options), default=0) + 2
        for i, option in enumerate(options):
            text = ("> " if i == selected else "  ") + option
            canvas.put(y, max(0, (cols - width) // 2), text, "gold" if i == selected else "default")
            y += 1
    if message:
        canvas.put(y + 1, max(0, (cols - len(message)) // 2), message, message_key)
    return canvas.grid
