"""A fork's event type, for tests: it only notes each stage it is shown."""

SEEN: list[str] = []


def on_stage(world, occurrence, stage):
    SEEN.append(stage)
    return []
