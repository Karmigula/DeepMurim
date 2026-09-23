"""What the player is told about masks and being seen through them."""

from narrate.outcomes import cap, outcome, summary

HOW = {"art": "They know that way of fighting.", "voice": "They know your voice.", "changing": "They saw your face."}


@outcome("mask_bought", body_facts=False)
def _bought(world, event):
    return ["You buy a plain mask."], {}


@outcome("mask_on", body_facts=False)
def _on(world, event):
    return [f"You are now {world.entity(event.data['persona']).name}."], {}


@outcome("mask_off", body_facts=False)
def _off(world, event):
    return ["You take off your mask."], {}


@outcome("recognised", body_facts=False)
def _recognised(world, event):
    name = cap(world.entity(event.actors[1]).name)
    return [f"{name} looks hard at you. {HOW[event.data['how']]}", "They know who is behind the mask."], {}


@summary("mask_bought")
def _bought_line(world, entry, names, place, other):
    return "Bought a mask."


@summary("mask_on")
def _on_line(world, entry, names, place, other):
    return f"Put on a mask as {world.entity(entry.data['persona']).name}."


@summary("mask_off")
def _off_line(world, entry, names, place, other):
    return "Took off the mask."


@summary("recognised")
def _recognised_line(world, entry, names, place, other):
    return f"{cap(other)} recognised you behind the mask."
