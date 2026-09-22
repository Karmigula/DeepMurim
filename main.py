"""DeepMurim. `python main.py` to play; `python main.py --smoke out.png` for a headless check."""

import os
import sys
import tempfile
from pathlib import Path


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
        app = App(config, beside("saves"), DEFAULT_PATH)
    screen = Screen(config)

    if smoke_png:
        for key, text in [("return", "\r"), *[(ch, ch) for ch in "Tester"], ("return", "\r"), ("1", "1")]:
            app.handle_key(key, text)
        screen.draw(app.grid(screen.cols, screen.rows))
        screen.screenshot(smoke_png)
        app.shutdown()
        screen.close()
        return

    clock = pygame.time.Clock()
    while app.running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                app.running = False
            elif event.type == pygame.VIDEORESIZE:
                screen.resize(event.size)
            elif event.type == pygame.KEYDOWN:
                key = pygame.key.name(event.key)
                if key == "f11":
                    screen.toggle_fullscreen()
                else:
                    app.handle_key(key, event.unicode)
        screen.draw(app.grid(screen.cols, screen.rows))
        screen.present()
        clock.tick(30)
    app.shutdown()
    screen.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    run(args[1] if len(args) >= 2 and args[0] == "--smoke" else None)
