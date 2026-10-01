"""Every size and colour in one place."""

from dataclasses import dataclass, field

Color = tuple[int, int, int]

PALETTE: dict[str, Color] = {
    "default": (205, 200, 190),
    "dim": (115, 112, 108),
    "system": (140, 140, 165),
    "player": (240, 220, 150),
    "npc": (150, 200, 230),
    "gold": (225, 185, 85),
    "jade": (90, 195, 145),
    "red": (205, 75, 65),
    "blue": (95, 145, 215),
    "sky": (125, 165, 215),
    "white": (235, 235, 230),
    "brown": (160, 115, 75),
    "green": (95, 165, 85),
    "grey": (145, 145, 145),
    "purple": (165, 115, 195),
    "rule": (70, 70, 80),
    "heading": (225, 185, 85),  # UI headings: gold, but never counted as prose
    "prose": (215, 205, 175),  # Claude's prose (phase 6): a soft parchment, apart from the engine's own lines
}


@dataclass
class Config:
    window_title: str = "DeepMurim"
    window_width: int = 1280
    window_height: int = 800
    font_path: str = "assets/fonts/IBMPlexMono-Regular.ttf"
    font_size: int = 16
    background_color: Color = (12, 12, 16)
    art_width: int = 40
    art_height: int = 18
    art_side: str = "left"
    show_art: bool = True
    ai_mode: str = "off"  # phase 6: off | assist | ai_only (F1)
    ai_backend: str = "claude_code"  # phase 6b: claude_code | opencode
    ai_models: dict = field(default_factory=dict)  # phase 6b: {backend: {"narrate": model, "talk": model}}


def config_from(values: dict) -> Config:
    """A Config with any valid stored preferences applied; bad values ignored."""
    config = Config()
    if values.get("art_side") in ("left", "right"):
        config.art_side = values["art_side"]
    if isinstance(values.get("show_art"), bool):
        config.show_art = values["show_art"]
    if values.get("ai_mode") in ("off", "assist", "ai_only"):
        config.ai_mode = values["ai_mode"]
    if values.get("ai_backend") in ("claude_code", "opencode"):
        config.ai_backend = values["ai_backend"]
    models = values.get("ai_models")
    if isinstance(models, dict):
        config.ai_models = {b: {r: m for r, m in v.items() if isinstance(m, str)} for b, v in models.items()
                            if b in ("claude_code", "opencode") and isinstance(v, dict)}
    return config
