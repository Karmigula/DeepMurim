"""DeepMurim.

    python main.py                          play
    python main.py --smoke out.png          headless render check
    python main.py --replay session.jsonl   re-run a recorded session and report differences
"""

import os
import sys
import tempfile
from pathlib import Path

MAX_CONSECUTIVE_FRAME_CRASHES = 30  # a crash every frame for a second means give up, report saved


def install_crash_hook(logs_dir: Path) -> None:
    """Anything that escapes everything else still leaves a report behind."""
    from debug.reports import write_crash_report

    original = sys.excepthook

    def hook(kind, exc, tb):
        try:
            path = write_crash_report(logs_dir, exc, {"where": "uncaught"}, [])
            print(f"DeepMurim crashed; report saved to {path}", file=sys.stderr)
        except Exception:
            pass
        original(kind, exc, tb)

    sys.excepthook = hook


def run(smoke_png: str | None = None) -> None:
    if smoke_png:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
    import pygame

    from app import App
    from config import config_from
    from paths import beside
    from render.screen import Screen
    from settings_store import DEFAULT_PATH, load_values

    if smoke_png:
        temp = Path(tempfile.mkdtemp())
        config = config_from({})
        app = App(config, temp / "saves", temp / "settings.json")
    else:
        config = config_from(load_values())
        app = App(config, beside("saves"), DEFAULT_PATH, logs_dir=beside("logs"))
        install_crash_hook(beside("logs"))
    screen = Screen(config)

    if smoke_png:
        for key, text in [("return", "\r"), *[(ch, ch) for ch in "Tester"], ("return", "\r"), ("return", "\r"), ("1", "1")]:
            app.handle_key(key, text)
        screen.draw(app.grid(screen.cols, screen.rows))
        screen.screenshot(smoke_png)
        app.shutdown()
        screen.close()
        return

    clock = pygame.time.Clock()
    held: set[int] = set()
    consecutive_crashes = 0
    while app.running:
        try:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    app.running = False
                elif event.type == pygame.VIDEORESIZE:
                    screen.resize(event.size)
                elif event.type == pygame.KEYUP:
                    held.discard(event.key)
                elif event.type == pygame.KEYDOWN:
                    repeat = event.key in held
                    held.add(event.key)
                    key = pygame.key.name(event.key)
                    if key == "f11":
                        if not repeat:
                            screen.toggle_fullscreen()
                    else:
                        app.handle_key(key, event.unicode, repeat=repeat)
            app.poll()  # Claude's prose, when it comes (phase 6)
            screen.draw(app.grid(screen.cols, screen.rows))
            screen.present()
            consecutive_crashes = 0
        except Exception as exc:
            consecutive_crashes += 1
            if consecutive_crashes == 1:
                app.record_crash(exc, "main loop")  # one report per run of identical frames
            if consecutive_crashes >= MAX_CONSECUTIVE_FRAME_CRASHES:
                app.shutdown()
                screen.close()
                raise
        clock.tick(30)
    app.shutdown()
    screen.close()


def run_replay(session: str) -> int:
    from debug.replay import replay

    work = Path(tempfile.mkdtemp(prefix="deepmurim-replay-"))
    result = replay(session, work)
    print(f"replayed {result.commands} commands from {session}")
    if not result.mismatches:
        print("identical: every turn matched the recording")
        return 0
    print(f"{len(result.mismatches)} mismatch(es):")
    for mismatch in result.mismatches:
        print(f"  - {mismatch}")
    return 1


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "--replay":
        sys.exit(run_replay(args[1]))
    run(args[1] if len(args) >= 2 and args[0] == "--smoke" else None)
