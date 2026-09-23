"""The living world in the engine (phase 4a spec 7): the clocks run as time passes, and you hear what changed."""

import systems.agendas as agendas  # also registers the agendas with the life clock
import systems.lives as lives
import systems.world_clock as clock
from engine.actions import Action
from narrate.gossip_text import rumour_text
from narrate.world_text import NEWS_KINDS
from systems.beliefs import CONF_DECAY, believe
from world.events import Event
from world.gen.materialize import people_at

CHILD_AGE = 12
CHILD_BARRED = frozenset({"challenge", "spar", "ask_follow", "sect_invite", "demand"})
MAX_NEWS = 3


def _child(entity) -> bool:
    return entity is not None and entity.kind == "person" and float(entity.data.get("age", 30)) < CHILD_AGE


class WorldMixin:
    _clock_seen: int | None = None
    _last_visit: int | None = None

    def _before_scene(self) -> None:
        super()._before_scene()
        clock.world_tick(self.world)  # start the faction clock the first time a scene is shown (spec §6)
        visits = dict(self.player.data.get("visits", {}))
        self._last_visit = visits.get(str(self.place.id))  # kept for the arrival news line
        visits[str(self.place.id)] = self.world.time
        self.world.update_data(self.player.id, visits=visits)
        for person in people_at(self.world, self.place.id, exclude=self.player.id):
            lives.catch_up(self.world, person.id)

    def _before_talk(self, npc_id) -> None:
        super()._before_talk(npc_id)
        if isinstance(npc_id, int) and self.world.entity(npc_id) is not None:
            lives.catch_up(self.world, npc_id)

    def _after_commit(self, ids: list, events: list) -> list:
        lines = super()._after_commit(ids, events)
        for event in events:
            if event.kind == "heard":
                variant = event.data.get("variant", {})
                for someone in (variant.get("actor"), variant.get("target")):
                    if isinstance(someone, int) and self.world.entity(someone) is not None:
                        lives.catch_up(self.world, someone)
        seen = self.world.time if self._clock_seen is None else self._clock_seen
        ran = clock.run_due(self.world)
        if ran and self.world.time - seen >= lives.SEASON:
            lines.append((f"The world moved on: {ran} season{'s' if ran > 1 else ''} pass.", "dim"))
        self._clock_seen = self.world.time
        return lines

    def _after_arrival(self) -> list:
        return super()._after_arrival() + self._local_news()

    def _local_news(self) -> list:
        """What the town says changed here since you last came (ruling 6), and who you knew that died."""
        world, me, town = self.world, self.player.id, self.place.id
        last, self._last_visit = self._last_visit, None
        if last is None:
            return []
        fresh = [(b, f) for b, f in world.known_facts(town)
                 if f.place == town and f.time > last and f.predicate in NEWS_KINDS]
        fresh = sorted(fresh, key=lambda p: (-p[1].weight, -p[1].id))[:MAX_NEWS]
        if not fresh:
            return []
        told = []
        for belief, fact in fresh:
            believe(world, me, fact.id, belief.variant, town, CONF_DECAY, belief.hops + 1, "gossip")
            told.append(rumour_text(world, belief.variant, me))
        return [("Much has changed here. " + " ".join(told), "dim")] + self._mourn([f for _, f in fresh])

    def _mourn(self, facts: list) -> list:
        me = self.player.id
        known = set(self.world.acquaintances(me))
        mourned = {e.actors[1] for e in self.world.chronicle_about(me, limit=200) if e.kind == "heard_death"}
        events = []
        for fact in facts:
            dead = fact.subject if fact.predicate == "died" else fact.object if fact.predicate == "killed" else None
            if dead in known and dead not in mourned and dead != me:
                mourned.add(dead)
                events.append(Event("heard_death", (me, dead), self.place.id, {"fact": fact.id}))
        return self._commit(events) if events else []

    def _presence_tag(self, person) -> str:
        tag = super()._presence_tag(person)
        age = person.data.get("age")
        if age is None:
            return tag
        if person.data.get("occupation") != "child":
            return f"{tag} ({int(age)})"
        here = {p.id for p in people_at(self.world, self.place.id)}
        parents = [p for p in agendas.parents_of(self.world, person.id) if p in here]
        of = f", child of {self.world.entity(parents[0]).name}" if parents else ""
        return f"{tag} ({int(age)}{of})"

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        return [c for c in extras if c.action.verb not in CHILD_BARRED] if _child(npc) else extras

    def _gate(self, action: Action):
        if action.verb in CHILD_BARRED:
            for target in (action.target, self.focus):  # "demand" names the duty; the child is who you face
                if isinstance(target, int) and _child(self.world.entity(target)):
                    return self._turn([("They are only a child.", "system")])
        return super()._gate(action)
