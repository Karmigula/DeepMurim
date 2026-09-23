"""Founding a sect in the engine (phase 3c spec 4): followers, and the founding menus."""

import systems.founding as founding
import systems.land as land
from engine.actions import Action, Choice

FOUND_MENUS = ("found_name", "found_path", "found_taboo", "found_trial", "found_ranks", "found_confirm")


class FoundingMixin:
    _founding: dict | None = None

    def _conversation_extras(self, npc) -> list:
        extras = super()._conversation_extras(npc)
        if founding.my_sect(self.world, self.player.id) is None and founding.can_ask_to_follow(self.world, npc.id, self.player.id):
            extras.append(Choice("Ask them to follow you", Action("ask_follow", npc.id)))
        return extras

    def _faction_options(self, npc) -> list:
        options = super()._faction_options(npc)
        town = self.place.id
        if land.magistrate_of(self.world, town) == npc.id and land.owner_of(self.world, town) == self.player.id \
                and founding.my_sect(self.world, self.player.id) is None:
            options.append(Choice("Found a sect", Action("found_menu")))
        return options

    def _submenu_options(self) -> dict:
        options = super()._submenu_options()
        if self.focus is not None and self.submenu in FOUND_MENUS:
            options[self.submenu] = (self._found_choices(self.submenu), Action("talk_menu"))
        return options

    def _found_choices(self, step: str) -> list:
        f = self._founding or {}
        if step == "found_name":
            return [Choice(n, Action("found_name", n)) for n in founding.name_suggestions(self.world, self.player.id)]
        if step == "found_path":
            return [Choice(p.capitalize(), Action("found_path", p)) for p in ("righteous", "neutral", "ruthless")]
        if step == "found_taboo":
            return [Choice(t.replace("_", " ").capitalize(), Action("found_taboo", t))
                    for t in founding.TABOOS if t not in f.get("taboos", [])]
        if step == "found_trial":
            return [Choice(f"Entry by {t}", Action("found_trial", t)) for t in founding.TRIALS]
        if step == "found_ranks":
            return [Choice(f"Ranks like a {k} ({founding.PRESETS[k][0]} first)", Action("found_ranks", k))
                    for k in founding.PRESETS]
        return [Choice(f"Found the {f.get('name')}", Action("found_confirm"))]

    def _do_ask_follow(self, npc):
        if self.focus != npc or not founding.can_ask_to_follow(self.world, npc, self.player.id):
            return self._turn([("They will not follow you.", "system")])
        return self._turn(self._commit(founding.sworn_events(self.world, self.player.id, npc, self.place.id)))

    def _found_step(self, step: str, prompt: str):
        self.submenu = step
        return self._turn([(prompt, "system")])

    def _do_found_menu(self, _target):
        town = self.place.id
        if self.focus != land.magistrate_of(self.world, town):
            return self._turn([("A charter is granted by the magistrate.", "system")])
        if (why := founding.found_block(self.world, self.player.id, town)) is not None:
            return self._turn([(why, "system")])
        self._founding = {"taboos": []}
        return self._found_step("found_name", "What will your sect be called?")

    def _do_found_name(self, name):
        if self._founding is None or name not in founding.name_suggestions(self.world, self.player.id):
            return self._turn([("Choose a name first.", "system")])
        self._founding["name"] = name
        return self._found_step("found_path", "Which path will it walk?")

    def _do_found_path(self, path):
        if self._founding is None or path not in ("righteous", "neutral", "ruthless"):
            return self._turn([("Choose a path.", "system")])
        self._founding["path"] = path
        return self._found_step("found_taboo", "Choose the first of two taboos.")

    def _do_found_taboo(self, taboo):
        if self._founding is None or taboo not in founding.TABOOS or taboo in self._founding["taboos"]:
            return self._turn([("Choose a taboo.", "system")])
        self._founding["taboos"].append(taboo)
        if len(self._founding["taboos"]) < 2:
            return self._found_step("found_taboo", "Choose the second taboo.")
        return self._found_step("found_trial", "How will newcomers prove themselves?")

    def _do_found_trial(self, trial):
        if self._founding is None or trial not in founding.TRIALS:
            return self._turn([("Choose an entry trial.", "system")])
        self._founding["trial"] = trial
        return self._found_step("found_ranks", "What will its ranks be called?")

    def _do_found_ranks(self, ranks):
        if self._founding is None or ranks not in founding.PRESETS:
            return self._turn([("Choose the ranks.", "system")])
        self._founding["ranks"] = ranks
        return self._found_step("found_confirm", "All is ready. Found it?")

    def _do_found_confirm(self, _target):
        f = self._founding or {}
        if not all(k in f for k in ("name", "path", "trial", "ranks")) or len(f.get("taboos", [])) != 2:
            return self._turn([("The founding is not ready.", "system")])
        town = self.place.id
        if (why := founding.found_block(self.world, self.player.id, town)) is not None:
            return self._turn([(why, "system")])
        self._founding, self.submenu = None, None
        return self._turn(self._commit(founding.founded_events(self.world, self.player.id, self.focus, town, f)))
