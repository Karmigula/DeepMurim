"""What the player is told about trade (phase 4c)."""

from narrate.outcomes import outcome, summary


@outcome("traded", body_facts=False)
def _traded(world, event):
    d = event.data
    verb = "buy" if d["side"] == "buy" else "sell"
    return [f"You {verb} {d['n']} {d['good']} for {d['total']} silver ({d['unit']} each)."], {}


@summary("traded")
def _traded_line(world, entry, names, place, other):
    d = entry.data
    return f"{'Bought' if d['side'] == 'buy' else 'Sold'} {d['n']} {d['good']} in {place} for {d['total']} silver."


@outcome("bought_mule", body_facts=False)
def _mule(world, event):
    return ["You buy a sturdy mule. It regards you without enthusiasm."], {}


@summary("bought_mule")
def _mule_line(world, entry, names, place, other):
    return f"Bought a mule in {place}."
