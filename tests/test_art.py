from render.art import art_width, blank, compose_portrait, compose_scene, load_art, parse_art, render_request, stamp
from world.gen.npc import PORTRAIT_PARTS
from world.gen.region import TERRAINS
from world.gen.town import KINDS


def test_markup_and_transparency():
    art = parse_art("; comment\n{red}ab {/}c\nd")
    assert art[0] == [("a", "red"), ("b", "red"), None, ("c", "default")]
    assert art[1] == [("d", "default")]


def test_colour_persists_across_lines():
    assert parse_art("{jade}a\nb")[1] == [("b", "jade")]


def test_stamp_clips():
    canvas = blank(3, 2)
    stamp(canvas, parse_art("abcd\nefgh\nijkl"), -1, 1)
    assert [len(r) for r in canvas] == [3, 3]
    assert canvas[0][1] == ("e", "default") and canvas[0][2] == ("f", "default")
    assert canvas[1][2] == ("j", "default")


def test_render_request_is_exact_size_even_when_tiny():
    for w, h in [(40, 18), (5, 3), (1, 1)]:
        for req in [
            {"type": "scene", "terrain": "river", "settlement": "town", "watch": 2},
            {"type": "portrait", "parts": {"hair": 0, "face": 0, "robe": 0}},
            {"type": "nonsense"},
        ]:
            art = render_request(req, w, h)
            assert len(art) == h and all(len(r) == w for r in art)


def test_missing_art_is_empty():
    assert load_art("does_not_exist") == []


def test_every_asset_exists_and_fits():
    names = [f"sky_{w}" for w in range(4)] + [f"terrain_{t}" for t in TERRAINS]
    names += [f"settlement_{k}" for k in set(KINDS)] + ["title"]
    names += [f"{part}_{n}" for part, count in PORTRAIT_PARTS.items() for n in range(count)]
    for name in names:
        art = load_art(name)
        assert art, name
        assert art_width(art) <= 40 and len(art) <= 18, name
    assert compose_scene("mountains", "city", 3, 40, 18)
    assert compose_portrait({"hair": 1, "face": 2, "robe": 3}, 40, 18)
