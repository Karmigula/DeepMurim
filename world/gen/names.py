"""Name tables. Chinese and Korean murim flavour, mixed on purpose."""

import random

SURNAMES = (
    "Li", "Wang", "Zhang", "Chen", "Zhao", "Namgung", "Jegal", "Dang", "Moyong", "Peng",
    "Hwang", "Baek", "Seo", "Mok", "Yeon", "Tang", "Ma", "Gu", "Jin", "Ha",
)
GIVEN_HEAD = (
    "Wei", "Jin", "Hao", "Mei", "Lan", "Tae", "Seo", "Yun", "Feng", "Ling",
    "Ho", "Min", "Rin", "Shen", "Kai", "Yeon", "Bo", "Xue", "Ha", "Do",
)
GIVEN_TAIL = ("", "", "long", "hwa", "yang", "ryeong", "an", "jun", "yu", "ming", "su", "hyun", "rou", "woo")
PLACE_PREFIX = (
    "Azure", "Jade", "Crimson", "White Crane", "Iron", "Misty", "Willow", "Plum Blossom",
    "Black Rock", "Golden", "Stone Bridge", "Autumn", "Red Cliff", "Cloud", "Pine",
    "Thunder", "Silver", "Falling Leaf", "Nine Bends", "Dragon Well",
)
SETTLEMENT_SUFFIX = {"village": "Village", "town": "Town", "city": "City"}
REGION_NOUN = {
    "plains": "Plains", "mountains": "Peaks", "river": "Riverlands",
    "forest": "Woods", "marsh": "Marshes", "hills": "Hills",
}


def person_name(rng: random.Random) -> tuple[str, str]:
    return rng.choice(SURNAMES), rng.choice(GIVEN_HEAD) + rng.choice(GIVEN_TAIL)


def place_name(rng: random.Random, suffix: str) -> str:
    return f"{rng.choice(PLACE_PREFIX)} {suffix}"
