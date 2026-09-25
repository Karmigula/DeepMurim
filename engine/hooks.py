"""Extension points for feature mixins (phase 2b).

Each mixin overrides what it needs and calls super(), so several features can
add to the same hook: Game(FeatureMixins..., GameHooks).
"""


class GameHooks:
    def _restore(self) -> None:
        """Rebuild in-progress state (a fight, an encounter) after a load."""

    def _gate(self, action):
        """Return a Turn to refuse an action in the current state, or None to allow it."""
        return None

    def _special_choices(self):
        """(shown, extra) that replace the normal menus, or None."""
        return None

    def _special_art(self):
        return None

    def _special_look(self):
        """Lines that replace the town scene on a look (inside a secret realm), or None."""
        return None

    def _special_status(self):
        return None

    def _conversation_extras(self, npc) -> list:
        return []

    def _conversation_hidden(self, npc) -> list:
        """Choices valid in conversation but reached only by typing (ask about <name>)."""
        return []

    def _general_extras(self) -> list:
        """Extra entries for the main menu's general group (rumours, masks)."""
        return []

    def _stamp(self, events: list) -> list:
        """Adjust events before they are committed (a mask stamps who the player seems to be)."""
        return events

    def _after_commit(self, ids: list, events: list) -> list:
        """Lines from reactions to what was just committed (someone seeing through a mask)."""
        return []

    def _status_suffix(self) -> str:
        return ""

    def _faction_options(self, npc) -> list:
        """Choices for the Faction matters... submenu with this person (phase 3b)."""
        return []

    def _presence_tag(self, person) -> str:
        """A short note after someone's name in the Here: line."""
        return ""

    def _presence_extras(self) -> list:
        """Lines after the Here: line (faction halls in this town)."""
        return []

    def _scene_extras(self) -> dict:
        """Extra keys for the town scene art (a hall overlay)."""
        return {}

    def _practise_extras(self, body) -> list:
        return []

    def _submenu_options(self) -> dict:
        """name -> (options, back action) for feature submenus."""
        return {}

    def _before_scene(self) -> None:
        """Bring the place up to date before it is described (phase 4a: people live their missed seasons)."""

    def _before_talk(self, npc_id) -> None:
        """Bring someone up to date before a conversation with them starts (phase 4a)."""

    def _after_arrival(self) -> list:
        return []

    def _after_look(self) -> list:
        return []

    def _after_duel(self, data: dict) -> list:
        return []
