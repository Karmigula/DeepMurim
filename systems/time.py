"""The calendar. One tick is a watch: four to a day."""

from world.db import World

WATCHES_PER_DAY = 4
DAYS_PER_SEASON = 90
SEASONS = ("Spring", "Summer", "Autumn", "Winter")
WATCH_NAMES = ("morning", "midday", "dusk", "night")


def _parts(t: int) -> tuple[int, str, int, str]:
    day = t // WATCHES_PER_DAY
    year = day // (DAYS_PER_SEASON * 4) + 1
    season = SEASONS[(day % (DAYS_PER_SEASON * 4)) // DAYS_PER_SEASON]
    return year, season, day % DAYS_PER_SEASON + 1, WATCH_NAMES[t % WATCHES_PER_DAY]


def season_of(t: int) -> str:
    return _parts(t)[1].lower()


def format_date(t: int) -> str:
    year, season, day, watch = _parts(t)
    return f"Year {year}, {season} day {day}, {watch}"


def format_season_year(t: int) -> str:
    year, season, _, _ = _parts(t)
    return f"the {season.lower()} of year {year}"


def advance(world: World, watches: int) -> None:
    world.set_time(world.time + watches)
