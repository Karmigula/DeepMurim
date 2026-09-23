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

    def _special_status(self):
        return None

    def _conversation_extras(self, npc) -> list:
        return []

    def _practise_extras(self, body) -> list:
        return []

    def _submenu_options(self) -> dict:
        """name -> (options, back action) for feature submenus."""
        return {}

    def _after_arrival(self) -> list:
        return []

    def _after_look(self) -> list:
        return []

    def _after_duel(self, data: dict) -> list:
        return []
