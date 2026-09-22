"""What the player is looking at and how keys change it. No pygame here:
keys arrive as pygame.key.name strings plus the typed text, so this is testable."""

import re
import time
from pathlib import Path

from config import PALETTE, Config
from engine.commands import parse
from engine.game import Game, Turn
from render.art import render_request
from render.layout import Grid, View, compose
from render.menu import compose_title
from settings_store import save_values
from world.db import SaveError

MAX_LOG = 500
MAX_COMMAND = 200
MAX_NAME = 24


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "hero"


class App:
    def __init__(self, config: Config, saves_dir: Path, settings_path: Path) -> None:
        self.config = config
        self.saves_dir = Path(saves_dir)
        self.settings_path = Path(settings_path)
        self.state = "title"
        self.running = True
        self.selected = 0
        self.message = ""
        self.name = ""
        self.game: Game | None = None
        self.log: list = []
        self.choices: list = []
        self.extra: list = []
        self.art: list = []
        self.status = ""
        self.command = ""
        self.scroll = 0

    # --- saves --------------------------------------------------------------
    def latest_save(self) -> Path | None:
        saves = sorted(self.saves_dir.glob("*.world"), key=lambda p: p.stat().st_mtime, reverse=True)
        return saves[0] if saves else None

    def title_options(self) -> list[str]:
        return (["Continue"] if self.latest_save() else []) + ["New world", "Quit"]

    # --- keys -----------------------------------------------------------------
    def handle_key(self, key: str, text: str) -> None:
        getattr(self, f"_{self.state}_key")(key, text)

    def _title_key(self, key: str, text: str) -> None:
        options = self.title_options()
        if key in ("up", "w"):
            self.selected = (self.selected - 1) % len(options)
        elif key in ("down", "s"):
            self.selected = (self.selected + 1) % len(options)
        elif key == "escape":
            self.running = False
        elif key in ("return", "enter"):
            choice = options[min(self.selected, len(options) - 1)]
            if choice == "Continue":
                self._continue()
            elif choice == "New world":
                self.state, self.name, self.message = "name", "", ""
            else:
                self.running = False

    def _name_key(self, key: str, text: str) -> None:
        if key == "escape":
            self.state = "title"
        elif key == "backspace":
            self.name = self.name[:-1]
        elif key in ("return", "enter"):
            self._start_new(self.name.strip() or "Nameless")
        elif len(text) == 1 and text.isprintable() and len(self.name) < MAX_NAME:
            self.name += text

    def _game_key(self, key: str, text: str) -> None:
        if key == "f2":
            self.config.art_side = "right" if self.config.art_side == "left" else "left"
            self._save_settings()
        elif key == "f3":
            self.config.show_art = not self.config.show_art
            self._save_settings()
        elif key == "page up":
            self.scroll += 5
        elif key == "page down":
            self.scroll = max(0, self.scroll - 5)
        elif key == "escape":
            if self.command:
                self.command = ""
            else:
                self._close_game()
                self.state, self.selected = "title", 0
        elif key == "backspace":
            self.command = self.command[:-1]
        elif key in ("return", "enter"):
            self.submit(self.command)
        elif len(text) == 1 and text.isprintable():
            if not self.command and text in "123456789":
                self.submit(text)
            elif len(self.command) < MAX_COMMAND:
                self.command += text

    # --- game -----------------------------------------------------------------
    def submit(self, text: str) -> None:
        action = parse(text, self.choices, self.extra)
        self.command = ""
        if action is None or self.game is None:
            return
        self.log.append((f"> {text.strip()}", "player"))
        self._show(self.game.perform(action))

    def _show(self, turn: Turn) -> None:
        if self.log:
            self.log.append(("", "default"))
        self.log.extend(turn.lines)
        del self.log[:-MAX_LOG]
        self.choices = turn.choices
        self.extra = turn.extra
        self.art = render_request(turn.art, self.config.art_width, self.config.art_height)
        self.status = turn.status
        self.scroll = 0

    def _start_new(self, name: str) -> None:
        path = self.saves_dir / f"{slug(name)}-{time.time_ns()}.world"
        self._close_game()
        self.game = Game.new(path, name)
        self.log = []
        self._show(self.game.start())
        self.state = "game"

    def _continue(self) -> None:
        path = self.latest_save()
        try:
            game = Game.load(path)
        except SaveError as exc:
            self.message = str(exc)
            return
        self._close_game()
        self.game, self.log, self.message = game, [], ""
        self._show(game.start())
        self.state = "game"

    def _close_game(self) -> None:
        if self.game is not None:
            self.game.close()
            self.game = None

    def _save_settings(self) -> None:
        save_values({"art_side": self.config.art_side, "show_art": self.config.show_art}, self.settings_path)

    def shutdown(self) -> None:
        self._close_game()

    # --- drawing ----------------------------------------------------------------
    def grid(self, cols: int, rows: int) -> Grid:
        if self.state == "title":
            return compose_title(cols, rows, PALETTE, self.title_options(), self.selected, self.message)
        if self.state == "name":
            return compose_title(cols, rows, PALETTE, [], 0, self.message, f"What is your name? {self.name}_")
        view = View(
            status=self.status, log=self.log, art=self.art,
            choices=[c.label for c in self.choices], command=self.command,
            art_side=self.config.art_side, show_art=self.config.show_art, scroll=self.scroll,
        )
        return compose(view, cols, rows, PALETTE, self.config.art_width)
