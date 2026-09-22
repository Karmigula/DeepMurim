from config import config_from
from settings_store import load_values, save_values


def test_roundtrip(tmp_path):
    path = tmp_path / "s.json"
    assert save_values({"art_side": "right"}, path)
    assert load_values(path) == {"art_side": "right"}


def test_missing_and_corrupt_give_empty(tmp_path):
    assert load_values(tmp_path / "nope.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    assert load_values(bad) == {}


def test_config_applies_settings():
    config = config_from({"art_side": "right", "show_art": False})
    assert config.art_side == "right"
    assert config.show_art is False


def test_config_ignores_bad_values():
    config = config_from({"art_side": "up", "show_art": "yes"})
    assert config.art_side == "left"
    assert config.show_art is True
