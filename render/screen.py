"""The pygame window: draws a grid of (char, colour) cells in a monospace font.

One of only two modules allowed to import pygame. Adapted from AsciiCrawler's
render/screen.py, with cells sized to the font rather than square.
"""

import pygame

from config import Config
from paths import bundled

FALLBACK = {"│": "|", "─": "-", "●": "o", "◐": "c", "◌": "o", "×": "x", "·": "."}


class Screen:
    def __init__(self, config: Config) -> None:
        pygame.init()
        pygame.key.set_repeat(400, 35)
        pygame.display.set_caption(config.window_title)
        self._config = config
        path = bundled(config.font_path)
        self._font = pygame.font.Font(str(path) if path.is_file() else None, config.font_size)
        self.cell_w = self._font.size("M")[0]
        self.cell_h = self._font.get_linesize()
        self._cache: dict = {}
        self._fullscreen = False
        self._windowed = (config.window_width, config.window_height)
        self._open(self._windowed, pygame.RESIZABLE)

    def _open(self, size, flags) -> None:
        self._window = pygame.display.set_mode(size, flags)
        width, height = self._window.get_size()
        self.cols = max(1, width // self.cell_w)
        self.rows = max(1, height // self.cell_h)

    def resize(self, size) -> None:
        if not self._fullscreen:
            self._windowed = size
            self._open(size, pygame.RESIZABLE)

    def toggle_fullscreen(self) -> None:
        """Borderless fullscreen on the desktop resolution, or back to the window."""
        self._fullscreen = not self._fullscreen
        if self._fullscreen:
            self._open((0, 0), pygame.NOFRAME)
        else:
            self._open(self._windowed, pygame.RESIZABLE)

    def draw(self, grid) -> None:
        self._window.fill(self._config.background_color)
        for r, row in enumerate(grid[: self.rows]):
            for c, cell in enumerate(row[: self.cols]):
                if cell is not None:
                    self._window.blit(self._glyph(*cell), (c * self.cell_w, r * self.cell_h))

    def _glyph(self, ch: str, colour) -> pygame.Surface:
        key = (ch, colour)
        if key not in self._cache:
            metrics = self._font.metrics(ch)
            if not metrics or metrics[0] is None:
                ch = FALLBACK.get(ch, "?")
            self._cache[key] = self._font.render(ch, True, colour)
        return self._cache[key]

    def present(self) -> None:
        pygame.display.flip()

    def screenshot(self, path) -> None:
        pygame.image.save(self._window, str(path))

    def close(self) -> None:
        pygame.quit()
