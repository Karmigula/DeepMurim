"""What the player is looking at and how keys change it. No pygame here:
keys arrive as pygame.key.name strings plus the typed text, so this is testable.

Also the home of the debug kit's live half: every session is logged, every
turn is checked against the invariants, and exceptions become crash reports
instead of a dead window.
"""

import re
import time
from collections import deque
from pathlib import Path

from config import PALETTE, Config
from debug.invariants import NARRATIVE, check_turn, check_world
from debug.reports import write_bug_report, write_crash_report
from debug.session import SessionLog, stamp
from engine.commands import parse
from engine.game import Game, Turn
from render.art import render_request
from render.layout import Grid, View, compose
from render.menu import compose_title
from settings_store import save_values
from systems.time import format_date
from world.db import SaveError

MAX_LOG = 500
MAX_COMMAND = 200
MAX_NAME = 24
MAX_VIOLATIONS = 200
INSTANT_KEYS = "123456789"  # submit on press, so a held key must not auto-repeat them


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "hero"


class App:
    def __init__(self, config: Config, saves_dir: Path, settings_path: Path, logs_dir: Path | None = None) -> None:
        self.config = config
        self.saves_dir = Path(saves_dir)
        self.settings_path = Path(settings_path)
        self.logs_dir = Path(logs_dir) if logs_dir is not None else self.saves_dir.parent / "logs"
        self.state = "title"
        self.running = True
        self.selected = 0
        self.message = ""
        self.name = ""
        self.game: Game | None = None
        self.save_path: Path | None = None
        self.log: list = []
        self.choices: list = []
        self.extra: list = []
        self.art: list = []
        self.status = ""
        self.command = ""
        self.scroll = 0
        # debug kit
        self.session: SessionLog | None = None
        self.last_turn: Turn | None = None
        self.crash_count = 0
        self.violations: list[str] = []
        self.debug_visible = False
        self.report_note = ""
        self._recent_narration: deque[str] = deque(maxlen=4)

    # --- saves --------------------------------------------------------------
    def latest_save(self) -> Path | None:
        saves = sorted(self.saves_dir.glob("*.world"), key=lambda p: p.stat().st_mtime, reverse=True)
        return saves[0] if saves else None

    def title_options(self) -> list[str]:
        return (["Continue"] if self.latest_save() else []) + ["New world", "Quit"]

    # --- keys -----------------------------------------------------------------
    def handle_key(self, key: str, text: str, repeat: bool = False) -> None:
        """`repeat` is True for key-repeat events from a held key."""
        if repeat and self.state == "game" and not self.command and len(text) == 1 and text in INSTANT_KEYS:
            return
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
                self.open_save(self.latest_save())
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
            self.start_new(self.name.strip() or "Nameless")
        elif len(text) == 1 and text.isprintable() and len(self.name) < MAX_NAME:
            self.name += text

    def _game_key(self, key: str, text: str) -> None:
        if key == "f2":
            self.config.art_side = "right" if self.config.art_side == "left" else "left"
            self._save_settings()
        elif key == "f3":
            self.config.show_art = not self.config.show_art
            self._save_settings()
        elif key == "f9":
            if self.command.strip():
                self.bug_report()
            else:
                self.state, self.report_note = "report", ""
        elif key == "f12":
            self.debug_visible = not self.debug_visible
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
            if not self.command and text in INSTANT_KEYS:
                self.submit(text)
            elif len(self.command) < MAX_COMMAND:
                self.command += text

    def _report_key(self, key: str, text: str) -> None:
        """F9 on an empty command line: ask for a description, Enter saves, Esc cancels."""
        if key == "escape":
            self.state = "game"
        elif key == "backspace":
            self.report_note = self.report_note[:-1]
        elif key in ("return", "enter"):
            self.command = self.report_note
            self.state = "game"
            self.bug_report()
        elif len(text) == 1 and text.isprintable() and len(self.report_note) < MAX_COMMAND:
            self.report_note += text

    # --- game -----------------------------------------------------------------
    def submit(self, text: str) -> None:
        action = parse(text, self.choices, self.extra)
        self.command = ""
        if action is None or self.game is None:
            return
        self.log.append((f"> {text.strip()}", "player"))
        self._record("command", text=text, verb=action.verb)
        try:
            turn = self.game.perform(action)
        except Exception as exc:  # the whole point: a bug becomes a report, not a dead game
            self.record_crash(exc, f"perform {action.verb}")
            return
        self._show(turn)

    def _show(self, turn: Turn) -> None:
        if self.log:
            self.log.append(("", "default"))
        self.log.extend(turn.lines)
        self.choices = turn.choices
        self.extra = turn.extra
        self.art = render_request(turn.art, self.config.art_width, self.config.art_height)
        self.status = turn.status
        self.scroll = 0
        self.last_turn = turn
        self._record(
            "turn", lines=[list(line) for line in turn.lines],
            choices=[c.label for c in turn.choices], status=turn.status, art=turn.art,
        )
        self._check(turn)
        del self.log[:-MAX_LOG]

    def _check(self, turn: Turn) -> None:
        try:
            problems = check_world(self.game.world) + check_turn(self.game, turn, list(self._recent_narration))
        except Exception as exc:
            problems = [f"invariant check itself failed: {exc!r}"]
        for text, key in turn.lines:
            if key in NARRATIVE and text:
                self._recent_narration.append(text)
        if problems:
            self.violations.extend(problems)
            del self.violations[:-MAX_VIOLATIONS]
            self._record("violation", problems=problems)
            more = f" (+{len(problems) - 1} more)" if len(problems) > 1 else ""
            self.log.append((f"debug: {problems[0][:90]}{more} - F12 for details, F9 to report", "red"))

    def start_new(self, name: str, world_seed: int | None = None) -> None:
        path = self.saves_dir / f"{slug(name)}-{time.time_ns()}.world"
        self._close_game()
        self.game = Game.new(path, name, world_seed=world_seed)
        self.save_path = path
        self._open_session(mode="new", player=name, seed=self.game.world.world_seed)
        self.log = []
        self._show(self.game.start())
        self.state = "game"

    def open_save(self, path: Path | None) -> bool:
        if path is None:
            self.message = "No save to continue"
            return False
        try:
            game = Game.load(path)
        except SaveError as exc:
            self.message = str(exc)
            return False
        self._close_game()
        self.game, self.save_path, self.log, self.message = game, Path(path), [], ""
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        snapshot = self.logs_dir / f"session-{stamp()}.start.world"
        game.world.backup_to(snapshot)
        self._open_session(mode="continue", player=game.player.name, seed=game.world.world_seed, snapshot=str(snapshot))
        self._show(game.start())
        self.state = "game"
        return True

    def _open_session(self, **header) -> None:
        self.session = SessionLog(self.logs_dir / f"session-{stamp()}.jsonl")
        self.session.record("session", save=str(self.save_path), **header)
        self._recent_narration.clear()

    def _record(self, kind: str, **data) -> None:
        if self.session is not None:
            self.session.record(kind, **data)

    def _close_game(self) -> None:
        if self.game is not None:
            self.game.close()
            self.game = None
        if self.session is not None:
            self.session.close()

    def _save_settings(self) -> None:
        save_values({"art_side": self.config.art_side, "show_art": self.config.show_art}, self.settings_path)

    def shutdown(self) -> None:
        self._close_game()

    # --- debug kit ----------------------------------------------------------------
    def debug_context(self, where: str = "") -> dict:
        context = {
            "where": where, "state": self.state, "save": str(self.save_path),
            "session_log": str(self.session.path) if self.session else None,
            "command_buffer": self.command, "crashes": self.crash_count,
            "recent_violations": self.violations[-5:],
        }
        game = self.game
        if game is not None:
            try:
                place = game.place
                context.update(
                    seed=game.world.world_seed, time=game.world.time, date=format_date(game.world.time),
                    place=f"{place.name} #{place.id}", focus=game.focus, submenu=game.submenu,
                )
            except Exception as exc:
                context["game_state_error"] = repr(exc)
        return context

    def record_crash(self, exc: BaseException, where: str) -> Path:
        self.crash_count += 1
        recent = list(self.session.recent) if self.session else []
        path = write_crash_report(self.logs_dir, exc, self.debug_context(where), recent)
        self._record("crash", error=repr(exc), where=where, report=str(path))
        self.log.append((
            f"Something went wrong ({type(exc).__name__}). A crash report was saved to {path.name}. "
            "Press F9 to save a full bug report.", "red",
        ))
        return path

    def bug_report(self) -> Path | None:
        if self.game is None:
            return None
        note, self.command = self.command.strip(), ""
        folder = write_bug_report(
            self.logs_dir, self.game.world, self.session, note,
            self.debug_context("bug report"), self.violations[-50:],
        )
        self._record("bug_report", note=note, folder=str(folder))
        self.log.append((f"Bug report saved to {folder} - hand that folder to Claude.", "gold"))
        return folder

    def debug_lines(self) -> list:
        context = self.debug_context("overlay")
        lines = [
            (f"place {context.get('place')} | {context.get('date')} (t={context.get('time')}) | "
             f"focus {context.get('focus')} | submenu {context.get('submenu')}", "gold"),
            (f"save: {context['save']}", "dim"),
            (f"session log: {context['session_log']}", "dim"),
            (f"crashes this session: {self.crash_count} | invariant violations: {len(self.violations)}", "dim"),
            ("", "default"),
            ("Narrator input this turn (what Haiku would get):", "gold"),
        ]
        briefs = self.game.last_briefs if self.game is not None else []
        for brief in briefs:
            lines += [(f"  {line}", "default") for line in brief.to_prompt().splitlines()]
            lines.append(("", "default"))
        if not briefs:
            lines.append(("  (none this turn)", "dim"))
        lines.append(("Recent violations:", "gold"))
        lines += [(f"  {v}", "red") for v in self.violations[-8:]] or [("  none", "dim")]
        return lines

    # --- drawing ----------------------------------------------------------------
    def grid(self, cols: int, rows: int) -> Grid:
        if self.state == "title":
            return compose_title(cols, rows, PALETTE, self.title_options(), self.selected, self.message)
        if self.state == "name":
            return compose_title(cols, rows, PALETTE, [], 0, self.message, f"What is your name? {self.name}_")
        status, log, command = self.status, self.log, self.command
        if self.state == "report":
            command = f"Describe the bug (Enter saves, Esc cancels): {self.report_note}"
        if self.debug_visible:
            seed = self.game.world.world_seed if self.game else "?"
            status = f"DEBUG (F12 closes) | seed {seed} | F9 reports a bug"
            log = self.debug_lines()
        view = View(
            status=status, log=log, art=self.art,
            choices=[c.label for c in self.choices], command=command,
            art_side=self.config.art_side, show_art=self.config.show_art,
            scroll=0 if self.debug_visible else self.scroll,
        )
        return compose(view, cols, rows, PALETTE, self.config.art_width)
