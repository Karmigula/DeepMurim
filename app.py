"""What the player is looking at and how keys change it. No pygame here:
keys arrive as pygame.key.name strings plus the typed text, so this is testable.

Also the home of the debug kit's live half: every session is logged, every
turn is checked against the invariants, and exceptions become crash reports
instead of a dead window.
"""

import re
import shutil
import time
from collections import deque
from pathlib import Path

from ai.narrate import MODE_WORDS, Narration
from config import PALETTE, Config
from debug.invariants import NARRATIVE, check_turn, check_world
from debug.reports import write_bug_report, write_crash_report
from debug.session import SessionLog, stamp
from engine.commands import parse
from engine.game import Game, Turn
from engine.sheet import sheet_lines
from render.art import render_request
from render.body_chart import body_chart
from render.layout import Grid, View, compose
from render.menu import compose_title
from settings_store import save_values
from systems.creation import (
    FLOW_POINT_COST, ORIGINS, POINT_BASE, POINT_MAX, POINT_POOL, CreationChoice, point_buy_problem, points_spent,
)
from systems.techniques import FORMS
from systems.time import format_date
from world.body import PHYSIQUE
from world.db import SaveError

MAX_LOG = 500
MAX_COMMAND = 200
MAX_NAME = 24
MAX_VIOLATIONS = 200
INSTANT_KEYS = "123456789"  # submit on press, so a held key must not auto-repeat them
CREATE_OPTIONS = ("Random (roll everything)", "Choose an origin", "Point-buy")
ORIGIN_KEYS = tuple(ORIGINS)
POINT_ROWS = PHYSIQUE + ("meridian openness", "form", "begin")


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "hero"


class App:
    def __init__(self, config: Config, saves_dir: Path, settings_path: Path, logs_dir: Path | None = None,
                 bridge=None) -> None:
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
        # character creation
        self.pending_name = ""
        self.origin_selected = 0
        self.points: dict = {}
        self.flow_points = 0
        self.form_index = 0
        self.points_row = 0
        # debug kit
        self.session: SessionLog | None = None
        self.last_turn: Turn | None = None
        self.crash_count = 0
        self.violations: list[str] = []
        self.debug_visible = False
        self.sheet_visible = False
        self.report_note = ""
        self._recent_narration: deque[str] = deque(maxlen=4)
        self.narration = Narration(bridge, config.ai_mode)  # phase 6: Claude's prose, F1

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
                self._newcomer_save = None
                self.state, self.name, self.message = "name", "", ""
            else:
                self.running = False

    def _name_key(self, key: str, text: str) -> None:
        if key == "escape":
            self.state = "title"
        elif key == "backspace":
            self.name = self.name[:-1]
        elif key in ("return", "enter"):
            self.pending_name = self.name.strip() or "Nameless"
            self.state, self.selected, self.message = "create", 0, ""
        elif len(text) == 1 and text.isprintable() and len(self.name) < MAX_NAME:
            self.name += text

    def _create_key(self, key: str, text: str) -> None:
        if key in ("up", "w"):
            self.selected = (self.selected - 1) % len(CREATE_OPTIONS)
        elif key in ("down", "s"):
            self.selected = (self.selected + 1) % len(CREATE_OPTIONS)
        elif key == "escape":
            self.state = "name"
        elif key in ("return", "enter"):
            if self.selected == 0:
                self.start_new(self.pending_name, creation=CreationChoice("random"))
            elif self.selected == 1:
                self.state, self.origin_selected = "origin", 0
            else:
                self.state, self.message = "points", ""
                self.points = {p: POINT_BASE for p in PHYSIQUE}
                self.flow_points, self.form_index, self.points_row = 0, 0, 0

    def _origin_key(self, key: str, text: str) -> None:
        if key in ("up", "w"):
            self.origin_selected = (self.origin_selected - 1) % len(ORIGIN_KEYS)
        elif key in ("down", "s"):
            self.origin_selected = (self.origin_selected + 1) % len(ORIGIN_KEYS)
        elif key == "escape":
            self.state = "create"
        elif key in ("return", "enter"):
            self.start_new(self.pending_name, creation=CreationChoice("origin", ORIGIN_KEYS[self.origin_selected]))

    def _points_key(self, key: str, text: str) -> None:
        if key == "up":
            self.points_row = max(0, self.points_row - 1)
        elif key == "down":
            self.points_row = min(len(POINT_ROWS) - 1, self.points_row + 1)
        elif key in ("left", "-") or text == "-":
            self._adjust(-1)
        elif key in ("right", "+", "=") or text in ("+", "="):
            self._adjust(1)
        elif key == "escape":
            self.state, self.message = "create", ""
        elif key in ("return", "enter"):
            if POINT_ROWS[self.points_row] != "begin":
                self.points_row += 1
                return
            problem = point_buy_problem(self.points, self.flow_points)
            if problem:
                self.message = problem
                return
            choice = CreationChoice("point_buy", physique=tuple(self.points.items()),
                                    flow_points=self.flow_points, form=FORMS[self.form_index])
            self.message = ""
            self.start_new(self.pending_name, creation=choice)

    def _adjust(self, delta: int) -> None:
        row = POINT_ROWS[self.points_row]
        left = POINT_POOL - points_spent(self.points, self.flow_points)
        if row in PHYSIQUE:
            value = self.points[row] + delta
            if POINT_BASE <= value <= POINT_MAX and (delta < 0 or left >= 1):
                self.points[row] = value
        elif row == "meridian openness":
            value = self.flow_points + delta
            if value >= 0 and (delta < 0 or left >= FLOW_POINT_COST):
                self.flow_points = value
        elif row == "form":
            self.form_index = (self.form_index + delta) % len(FORMS)

    def _game_key(self, key: str, text: str) -> None:
        if key == "f1":
            self._cycle_ai()
        elif key == "f2":
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
            self.sheet_visible = self.sheet_visible and not self.debug_visible
        elif key == "f6":
            self.submit("standing")
        elif key == "f7":
            self.submit("ledger")
        elif key == "f8":
            self.submit("lineage")
        elif key == "f10":
            self.submit("rankings")
        elif key == "f11":
            self.submit("tournaments")
        elif key == "f5":
            self.submit("realms")
        elif key == "f4":
            self.sheet_visible = not self.sheet_visible
            self.debug_visible = self.debug_visible and not self.sheet_visible
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
        self._follow_exit()

    def _follow_exit(self) -> None:
        """After a death the player may leave for a new world or a newcomer (phase 4b spec 5.3)."""
        exit_to = getattr(self.game, "exit_to", None) if self.game is not None else None
        if exit_to == "title":
            self._close_game()
            self.state, self.selected = "title", 0
        elif exit_to == "newcomer":
            self._newcomer_save = self.save_path
            self._close_game()
            self.state, self.name, self.message = "name", "", ""

    def _cycle_ai(self) -> None:
        mode = self.narration.cycle()
        why = self.narration.unavailable() if mode != "off" else None
        if why is not None:
            self.narration.mode = mode = "off"
            self.log.append((f"Claude's prose cannot be used: {why}.", "system"))
        else:
            self.log.append((MODE_WORDS[mode] + ".", "system"))
        self.config.ai_mode = mode
        self._save_settings()

    def poll(self) -> None:
        """Every frame: Claude's prose for the last turn, if it has come (phase 6)."""
        if self.game is None or self.narration.pending is None and not getattr(self.narration.bridge, "just_paused", False):
            return
        waiting = self.narration.pending
        self.log.extend(self.narration.poll(self.log, self.game))
        if waiting is not None and self.narration.pending is None:
            self._record("ai", job="narrate", refused=self.narration.refused)

    def _show(self, turn: Turn) -> None:
        self.narration.settle(self.log)  # a turn left before its prose came keeps its own text
        if self.log:
            self.log.append(("", "default"))
        self.log.extend(turn.lines)
        start = len(self.log) - len(turn.lines)
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
        before = len(self.log)
        del self.log[:-MAX_LOG]
        if self.game is not None:
            self.narration.start(self.log, start - (before - len(self.log)), turn, self.game)

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

    def start_new(self, name: str, world_seed: int | None = None, creation: CreationChoice | None = None) -> None:
        creation = creation or CreationChoice()
        newcomer_save = getattr(self, "_newcomer_save", None)
        if newcomer_save is not None:  # a newcomer walks into the dead player's world (phase 4b)
            self._newcomer_save = None
            self._close_game()
            self.logs_dir.mkdir(parents=True, exist_ok=True)
            snapshot = self.logs_dir / f"session-{stamp()}.start.world"
            shutil.copyfile(newcomer_save, snapshot)  # the dead world, before the newcomer walks in: replayable
            self.game = Game.newcomer(newcomer_save, name, creation=creation)
            self.save_path = newcomer_save
            self._open_session(mode="newcomer", player=name, seed=self.game.world.world_seed,
                               creation=creation.to_dict(), snapshot=str(snapshot))
            self.log = []
            self._show(self.game.start())
            self.state = "game"
            return
        path = self.saves_dir / f"{slug(name)}-{time.time_ns()}.world"
        self._close_game()
        self.game = Game.new(path, name, world_seed=world_seed, creation=creation)
        self.save_path = path
        self._open_session(mode="new", player=name, seed=self.game.world.world_seed, creation=creation.to_dict())
        self.log = []
        self._show(self.game.start())
        self.state = "game"

    def open_save(self, path: Path | None) -> bool:
        if path is None:
            self.message = "No save to continue"
            return False
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        snapshot = self.logs_dir / f"session-{stamp()}.start.world"
        try:
            shutil.copyfile(path, snapshot)  # before loading: loading may migrate the save
        except OSError as exc:
            self.message = f"Could not read {Path(path).name} ({exc})"
            return False
        try:
            game = Game.load(path)
        except SaveError as exc:
            self.message = str(exc)
            snapshot.unlink(missing_ok=True)
            return False
        self._close_game()
        self.game, self.save_path, self.log, self.message = game, Path(path), [], ""
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
        self.narration.pending = None
        if self.game is not None:
            self.game.close()
            self.game = None
        if self.session is not None:
            self.session.close()

    def _save_settings(self) -> None:
        save_values({"art_side": self.config.art_side, "show_art": self.config.show_art,
                     "ai_mode": self.config.ai_mode}, self.settings_path)

    def shutdown(self) -> None:
        self._close_game()
        self.narration.close()

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
                here = game.world.targets(game.player.id, "located_in") \
                    or game.world.targets(game.player.id, "buried_at")  # the dead lie where they fell
                place = game.world.entity(here[0])
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
        if self.state == "create":
            return compose_title(cols, rows, PALETTE, list(CREATE_OPTIONS), self.selected,
                                 f"Who is {self.pending_name}?", message_key="dim")
        if self.state == "origin":
            origin = ORIGINS[ORIGIN_KEYS[self.origin_selected]]
            return compose_title(cols, rows, PALETTE, [ORIGINS[k].title for k in ORIGIN_KEYS],
                                 self.origin_selected, origin.description, message_key="dim")
        if self.state == "points":
            left = POINT_POOL - points_spent(self.points, self.flow_points)
            options = [f"{p:<18}{self.points[p]:>3}" for p in PHYSIQUE]
            options += [f"{'meridian openness':<18}{self.flow_points:>3}", f"{'form':<18}{FORMS[self.form_index]:>8}", "Begin"]
            note = self.message or f"Points left: {left}   (left/right adjusts, Enter on Begin starts)"
            return compose_title(cols, rows, PALETTE, options, self.points_row, note,
                                 message_key="red" if self.message else "dim")
        status, log, command, art = self.status, self.log, self.command, self.art
        if self.state == "report":
            command = f"Describe the bug (Enter saves, Esc cancels): {self.report_note}"
        if self.debug_visible:
            seed = self.game.world.world_seed if self.game else "?"
            status = f"DEBUG (F12 closes) | seed {seed} | F9 reports a bug"
            log = self.debug_lines()
        if self.sheet_visible and self.game is not None:
            status = "CHARACTER SHEET (F4 closes)"
            log = sheet_lines(self.game.world, self.game.player.id)
            art = body_chart(self.game.body(), self.game.world.time, self.config.art_width, self.config.art_height)
        view = View(
            status=status, log=log, art=art,
            choices=[c.label for c in self.choices], command=command,
            art_side=self.config.art_side, show_art=self.config.show_art,
            scroll=0 if self.debug_visible or self.sheet_visible else self.scroll,
        )
        return compose(view, cols, rows, PALETTE, self.config.art_width)
