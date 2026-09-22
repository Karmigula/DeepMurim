"""The game screen as a grid of (char, colour) cells. No pygame.

  row 0            status
  row 1            rule
  rows 2..         art frame | log      (art frame docks left or right)
  rule
  choices (up to 9)
  last row         > command
"""

import textwrap
from collections.abc import Sequence
from dataclasses import dataclass

from config import Color
from narrate.base import Line
from render.art import Art, art_width

Cell = tuple[str, Color] | None
Grid = list[list[Cell]]
MIN_LOG_WIDTH = 30


@dataclass
class View:
    status: str
    log: Sequence[Line]
    art: Art
    choices: Sequence[str]
    command: str
    art_side: str = "left"
    show_art: bool = True
    scroll: int = 0


def row_text(grid: Grid, r: int) -> str:
    return "".join(cell[0] if cell else " " for cell in grid[r])


class _Canvas:
    def __init__(self, cols: int, rows: int, palette: dict[str, Color]) -> None:
        self.cols, self.rows, self.palette = cols, rows, palette
        self.grid: Grid = [[None] * cols for _ in range(rows)]

    def colour(self, key: str) -> Color:
        return self.palette.get(key, self.palette["default"])

    def put(self, r: int, c: int, text: str, key: str) -> None:
        if not 0 <= r < self.rows:
            return
        colour = self.colour(key)
        for i, ch in enumerate(text):
            if 0 <= c + i < self.cols and ch != " ":
                self.grid[r][c + i] = (ch, colour)

    def hline(self, r: int) -> None:
        self.put(r, 0, "─" * self.cols, "rule")

    def vline(self, c: int, top: int, bottom: int) -> None:
        for r in range(top, bottom):
            self.put(r, c, "│", "rule")


def compose(view: View, cols: int, rows: int, palette: dict[str, Color], art_cols: int) -> Grid:
    canvas = _Canvas(cols, rows, palette)
    canvas.put(0, 1, view.status[: max(0, cols - 2)], "gold")
    if rows < 4:
        return canvas.grid
    canvas.hline(1)
    command_row = rows - 1
    visible = view.command[-max(1, cols - 3):]
    canvas.put(command_row, 0, f"> {visible}_", "player")

    choice_rows = max(0, min(len(view.choices), 9, (rows - 5) // 2))
    choice_top = command_row - choice_rows
    for k, label in enumerate(view.choices[:choice_rows]):
        canvas.put(choice_top + k, 1, f"{k + 1}) {label}"[: max(0, cols - 2)], "jade")
    canvas.hline(choice_top - 1)

    body_top, body_bottom = 2, choice_top - 1
    body_h = body_bottom - body_top
    if body_h <= 0:
        return canvas.grid

    show_art = view.show_art and cols - art_cols - 1 >= MIN_LOG_WIDTH + 2 and body_h >= 3
    if show_art:
        if view.art_side == "left":
            art_left, divider, log_left = 0, art_cols, art_cols + 2
        else:
            art_left, divider, log_left = cols - art_cols, cols - art_cols - 1, 1
        log_width = cols - art_cols - 3
        canvas.vline(divider, body_top, body_bottom)
        _draw_art(canvas, view.art, art_left, art_cols, body_top, body_h)
    else:
        log_left, log_width = 1, max(1, cols - 2)

    wrapped: list[Line] = []
    for text, key in view.log:
        for piece in textwrap.wrap(text, log_width) or [""]:
            wrapped.append((piece, key))
    scroll = min(max(0, view.scroll), max(0, len(wrapped) - body_h))
    end = len(wrapped) - scroll
    for k, (piece, key) in enumerate(wrapped[max(0, end - body_h):end]):
        canvas.put(body_top + k, log_left, piece, key)
    return canvas.grid


def _draw_art(canvas: _Canvas, art: Art, left: int, width: int, top: int, height: int) -> None:
    top += max(0, (height - len(art)) // 2)
    left += max(0, (width - art_width(art)) // 2)
    for r, row in enumerate(art[:height]):
        for c, cell in enumerate(row[:width]):
            if cell is not None:
                canvas.put(top + r, left + c, cell[0], cell[1])
