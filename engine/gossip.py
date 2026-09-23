"""News, telling and the Rumours page in the engine (phase 3a spec 7)."""

import systems.rumours as rumours
import systems.talk as talk
import systems.telling as telling
from engine.actions import Action, Choice
from narrate.gossip_text import rumour_text, who
from systems.beliefs import apparent_to, confidence_word, knowledge_of, known_people
from systems.facts import make_variant
from systems.kin import ensure_kin
from systems.reputation import reputation
from world.events import Event, Witness
from world.gen.materialize import people_at

MAX_PASS_ON = 7
MAX_PEOPLE = 8
MAX_RUMOURS = 20
INVENT_LABELS = {
    "killed": "Say that someone killed someone", "robbed": "Say that someone robbed someone",
    "fled_from": "Say that someone fled from a fight", "owns_manual": "Say that someone owns a secret manual",
}
GOSSIP_MENUS = ("tell", "invent_pred", "invent_subject", "invent_object")


class GossipMixin:
    _invent: dict | None = None

    # --- state ------------------------------------------------------------------------------
    def _restore(self) -> None:
        super()._restore()
        rumours.catch_up(self.world, self.place.id)

    def _after_arrival(self) -> list:
        lines = super()._after_arrival()
        rumours.catch_up(self.world, self.place.id)
        lines += self._fame()
        if self.encounter is None:
            lines += self._exposures()
        return lines

    def _fame(self) -> list:
        """What arriving here feels like, given what the town has heard."""
        rep = reputation(self.world, self.place.id, apparent_to(self.world, self.place.id, self.player.id))
        if rep.epithet:
            return [(f"People here know you as the {rep.epithet}.", "dim")]
        if rep.renown >= 2.0:
            return [("Some people here have heard of you.", "dim")]
        return []

    def _exposures(self) -> list:
        events = telling.exposure_events(self.world, self.player.id, self.place.id)
        return self._commit(events) if events else []

    # --- menus --------------------------------------------------------------------------------
    def _conversation_extras(self, npc) -> list:
        return [Choice("Ask for news", Action("news")), Choice("Tell them something...", Action("tell_menu"))] \
            + super()._conversation_extras(npc)

    def _conversation_hidden(self, npc) -> list:
        hidden = super()._conversation_hidden(npc)
        here = [p.id for p in people_at(self.world, self.place.id, exclude=self.player.id)]
        for someone in dict.fromkeys([self.player.id, *here, *known_people(self.world, self.player.id)]):
            if someone != npc.id:
                name = self.world.entity(someone).name
                hidden.append(Choice(f"Ask what they know of {name}", Action("ask_about", someone)))
        return hidden

    def _general_extras(self) -> list:
        extras = super()._general_extras()
        if self.world.beliefs(self.player.id):
            extras.append(Choice("Rumours you have heard", Action("rumours")))
        return extras

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        if self.focus is not None and self.submenu in GOSSIP_MENUS:
            options[self.submenu] = self._gossip_menu(self.submenu)
        return options

    def _gossip_menu(self, name: str):
        if name == "tell":
            return self._tell_choices(), Action("talk_menu")
        if name == "invent_pred":
            return [Choice(label, Action("invent_pred", p)) for p, label in INVENT_LABELS.items()], Action("tell_menu")
        exclude = ((self._invent or {}).get("subject"),) if name == "invent_object" else ()
        return [Choice(self.world.entity(p).name, Action(name, p)) for p in self._candidates(exclude)], \
            Action("invent_menu")

    def _tell_choices(self) -> list[Choice]:
        theirs = {(b.fact_id, b.variant_key) for b, _ in knowledge_of(self.world, self.focus)}
        mine = [(b, f) for b, f in self.world.known_facts(self.player.id) if (b.fact_id, b.variant_key) not in theirs]
        mine.sort(key=lambda p: (-p[1].time, -p[1].id))
        choices = [Choice(f"Tell them: {rumour_text(self.world, b.variant, self.player.id)}",
                          Action("tell", (b.fact_id, b.variant_key))) for b, _ in mine[:MAX_PASS_ON]]
        return choices + [Choice("Invent a rumour...", Action("invent_menu"))]

    def _candidates(self, exclude=()) -> list[int]:
        """People the player could tell tales about: met or heard of, alive, not the listener."""
        out = []
        for someone in known_people(self.world, self.player.id):
            entity = self.world.entity(someone)
            if entity.kind == "person" and not entity.data.get("dead") and not entity.data.get("beast") \
                    and someone not in exclude and someone != self.focus:
                out.append(someone)
        return out[:MAX_PEOPLE]

    # --- hearing --------------------------------------------------------------------------------
    def _do_news(self, _target):
        if self.focus is None:
            return self._turn([("Ask whom?", "system")])
        npc, me, place = self.world.entity(self.focus), self.player.id, self.place.id
        if (lost := self._lost_patience(npc, "news")) is not None:
            return lost
        rumours.catch_up(self.world, place)
        found = rumours.pick_news(self.world, npc.id, me)
        events = talk.ask_events(me, npc.id, place, "news")
        events += rumours.heard_events(self.world, me, npc.id, place, *found) if found \
            else rumours.no_news_events(me, npc.id, place)
        return self._turn(self._commit(events) + self._exposures())

    def _do_ask_about(self, someone):
        if self.focus is None:
            return self._turn([("Ask whom?", "system")])
        subject = self.world.entity(someone) if isinstance(someone, int) else None
        if subject is None or subject.kind not in ("person", "persona") or someone == self.focus:
            return self._turn([("Ask about whom?", "system")])
        npc, me, place = self.world.entity(self.focus), self.player.id, self.place.id
        topic = f"about {subject.name}"
        if (lost := self._lost_patience(npc, topic)) is not None:
            return lost
        rumours.catch_up(self.world, place)
        ensure_kin(self.world, subject.id)
        found = rumours.news_about(self.world, npc.id, subject.id)
        # The one asked about is a third actor: asking makes them someone the player has heard of.
        events = [Event("asked", (me, npc.id, subject.id), place, {"topic": topic},
                        witnesses=(Witness(npc.id, "engaged", 0.1),))]
        events += rumours.heard_events(self.world, me, npc.id, place, *found) if found \
            else rumours.no_news_events(me, npc.id, place, subject.name)
        return self._turn(self._commit(events) + self._exposures())

    # --- telling ----------------------------------------------------------------------------------
    def _do_tell_menu(self, _target):
        if self.focus is None:
            return self._turn([("Tell whom?", "system")])
        self.submenu = "tell"
        return self._turn([("What will you tell them?", "system")])

    def _do_tell(self, key):
        if self.focus is None:
            return self._turn([("Tell whom?", "system")])
        belief = next((b for b in self.world.beliefs(self.player.id)
                       if isinstance(key, tuple) and (b.fact_id, b.variant_key) == tuple(key)), None)
        if belief is None:
            return self._turn([("You don't know that.", "system")])
        events = telling.tell_events(self.world, self.player.id, self.focus, self.place.id, belief.variant,
                                     belief.fact_id, self._speaker())
        self.submenu = None
        return self._turn(self._commit(events) + self._exposures())

    def _do_invent_menu(self, _target):
        if self.focus is None:
            return self._turn([("Tell whom?", "system")])
        self._invent = {}
        self.submenu = "invent_pred"
        return self._turn([("What will you claim?", "system")])

    def _do_invent_pred(self, predicate):
        if self.focus is None or predicate not in INVENT_LABELS:
            return self._turn([("Claim what?", "system")])
        self._invent = {"pred": predicate}
        self.submenu = "invent_subject"
        return self._turn([("About whom?", "system")])

    def _do_invent_subject(self, someone):
        if self.focus is None or not self._invent or someone not in self._candidates():
            return self._turn([("About whom?", "system")])
        self._invent["subject"] = someone
        if self._invent["pred"] in telling.NEEDS_OBJECT:
            self.submenu = "invent_object"
            return self._turn([("And who was on the other end of it?", "system")])
        return self._tell_lie()

    def _do_invent_object(self, someone):
        if self.focus is None or not self._invent or "subject" not in self._invent \
                or someone not in self._candidates((self._invent["subject"],)):
            return self._turn([("Who, then?", "system")])
        self._invent["object"] = someone
        return self._tell_lie()

    def _tell_lie(self):
        claim, self._invent, self.submenu = self._invent, None, None
        story = make_variant(claim["pred"], claim["subject"], claim.get("object"), place=self.place.name)
        events = telling.tell_events(self.world, self.player.id, self.focus, self.place.id, story, None,
                                     self._speaker())
        return self._turn(self._commit(events) + self._exposures())

    def _speaker(self) -> int:
        """Who the listener takes the teller to be: the persona while masked and unrecognised."""
        return apparent_to(self.world, self.focus, self.player.id)

    # --- the Rumours page ----------------------------------------------------------------------
    def _do_rumours(self, _target):
        me = self.player.id
        by_fact: dict = {}
        for belief, fact in self.world.known_facts(me):
            by_fact.setdefault(fact.id, (fact, []))[1].append(belief)
        if not by_fact:
            return self._turn([("You have heard no rumours yet.", "system")])
        groups: dict = {}
        for fact, beliefs in sorted(by_fact.values(), key=lambda p: (-p[0].time, -p[0].id))[:MAX_RUMOURS]:
            beliefs.sort(key=lambda b: -b.confidence)
            groups.setdefault(beliefs[0].variant.get("actor"), []).append(beliefs)
        lines = [("Rumours you have heard:", "heading")]
        for actor, stories in groups.items():
            lines.append((f"About {who(self.world, actor, me)}:", "heading"))
            for beliefs in stories:
                settled = any(b.hops == 0 or b.confidence >= 0.75 for b in beliefs)
                for n, belief in enumerate(beliefs):
                    lead = "  " if n == 0 else "    or: "
                    mark = " Settled." if settled and n == 0 and len(beliefs) > 1 else ""
                    text = rumour_text(self.world, belief.variant, me)
                    lines.append((f"{lead}{text} ({self._provenance(belief)}){mark}", "dim"))
        return self._turn(lines)

    def _provenance(self, belief) -> str:
        word = confidence_word(belief)
        source = self.world.entity(belief.source) if belief.source is not None else None
        if belief.hops == 0 or source is None:
            return word
        if source.kind == "town":
            return f"{word}, gossip in {source.name}"
        return f"{word}, told by {source.name}"
