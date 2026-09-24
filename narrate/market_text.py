"""What the player is told about trade (phase 4c)."""

from narrate.gossip_text import SPECIAL_PHRASES
from narrate.outcomes import outcome, summary


def _market_story(world, variant, viewer) -> str:
    good = str(variant.get("good", "trade")).capitalize()
    where = variant.get("place") or "some town"
    if variant.get("predicate") == "shortage":
        return f"{good} is dear in {where}."
    return f"{good} is going cheap in {where}."


SPECIAL_PHRASES.update({"shortage": _market_story, "glut": _market_story})


@outcome("traded", body_facts=False)
def _traded(world, event):
    d = event.data
    verb = "buy" if d["side"] == "buy" else "sell"
    return [f"You {verb} {d['n']} {d['good']} for {d['total']} silver ({d['unit']} each)."], {}


@summary("traded")
def _traded_line(world, entry, names, place, other):
    d = entry.data
    return f"{'Bought' if d['side'] == 'buy' else 'Sold'} {d['n']} {d['good']} in {place} for {d['total']} silver."


def _goods_words(goods: dict) -> str:
    return ", ".join(f"{n} {g}" for g, n in sorted(goods.items())) or "nothing"


@outcome("lost_goods", body_facts=False)
def _lost(world, event):
    d = event.data
    taker = world.entity(event.actors[1]).name
    mule = " and your mule" if d["mule"] else ""
    if d["reason"] == "toll":
        return [f"{taker} takes {_goods_words(d['goods'])} as the toll."], {}
    return [f"{taker} takes {_goods_words(d['goods'])}{mule} from your pack."], {}


@summary("lost_goods")
def _lost_line(world, entry, names, place, other):
    d = entry.data
    mule = " and a mule" if d.get("mule") else ""
    why = "as a toll to" if d.get("reason") == "toll" else "to"
    return f"Lost {_goods_words(d['goods'])}{mule} {why} {other}."


@outcome("bought_mule", body_facts=False)
def _mule(world, event):
    return ["You buy a sturdy mule. It regards you without enthusiasm."], {}


@summary("bought_mule")
def _mule_line(world, entry, names, place, other):
    return f"Bought a mule in {place}."
