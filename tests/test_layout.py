from config import PALETTE
from render.art import parse_art
from render.layout import View, compose, row_text
from render.menu import compose_title

ART = parse_art("\n".join(["@" * 10] * 4))


def view(**kw):
    base = dict(status="Hero | mortal", log=[("hello world", "default")], art=ART,
                choices=["Look around", "Read your journal"], command="tal", art_side="left", show_art=True)
    base.update(kw)
    return View(**base)


def body_rows(grid):
    return [row_text(grid, r) for r in range(2, len(grid) - 4)]


def test_art_left():
    grid = compose(view(), 100, 30, PALETTE, 40)
    rows = body_rows(grid)
    assert any("@" in r[:40] for r in rows) and not any("@" in r[40:] for r in rows)
    assert any(r[42:].startswith("hello world") for r in rows)


def test_art_right():
    grid = compose(view(art_side="right"), 100, 30, PALETTE, 40)
    rows = body_rows(grid)
    assert any("@" in r[60:] for r in rows) and not any("@" in r[:60] for r in rows)
    assert any(r[1:].startswith("hello world") for r in rows)


def test_art_hidden():
    grid = compose(view(show_art=False), 100, 30, PALETTE, 40)
    assert not any("@" in r for r in body_rows(grid))
    assert any(r[1:].startswith("hello world") for r in body_rows(grid))


def test_too_narrow_hides_art():
    grid = compose(view(), 60, 30, PALETTE, 40)
    assert not any("@" in r for r in body_rows(grid))


def test_status_choices_and_command():
    grid = compose(view(), 100, 30, PALETTE, 40)
    assert "Hero | mortal" in row_text(grid, 0)
    assert row_text(grid, 29).startswith("> tal_")
    assert row_text(grid, 27).strip() == "1) Look around"
    assert row_text(grid, 28).strip() == "2) Read your journal"


def test_log_scrolls_and_wraps():
    log = [(f"line {n}", "default") for n in range(100)]
    grid = compose(view(log=log, show_art=False), 100, 30, PALETTE, 40)
    text = "\n".join(body_rows(grid))
    assert "line 99" in text and "line 10 " not in text
    grid = compose(view(log=log, show_art=False, scroll=50), 100, 30, PALETTE, 40)
    assert "line 49" in "\n".join(body_rows(grid)) and "line 99" not in "\n".join(body_rows(grid))
    long = [("word " * 100, "default")]
    grid = compose(view(log=long, show_art=False), 50, 30, PALETTE, 40)
    assert sum("word" in r for r in body_rows(grid)) > 5


def test_tiny_windows_keep_exact_size():
    for cols, rows in [(20, 6), (1, 1), (5, 2), (41, 3)]:
        grid = compose(view(), cols, rows, PALETTE, 40)
        assert len(grid) == rows and all(len(r) == cols for r in grid)
        title = compose_title(cols, rows, PALETTE, ["New world", "Quit"], 0, "oops", "Name: _")
        assert len(title) == rows and all(len(r) == cols for r in title)


def test_title_marks_selection_and_message():
    grid = compose_title(100, 40, PALETTE, ["Continue", "New world", "Quit"], 1, "Bad save")
    text = "\n".join(row_text(grid, r) for r in range(40))
    assert "> New world" in text and "  Continue" in text and "Bad save" in text
