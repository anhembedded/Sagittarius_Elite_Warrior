"""`EPIC-043B` — the colour scheme the person chose, one for the whole application.

The choice is System (the default: the platform's own light or dark), Light or Dark. It is a
property of the person's desktop, not of a screen, so one object holds it and everything that
cares follows it (`DisplayTimezonePreference` is the same shape), remembered across sessions
through `ui_state`. It holds only the choice; asking Qt to draw it is `colour_scheme_applier`
alone, and the application writes no palette, style sheet or colour for it
(`ui-presentation-rule.md` §1).

Capability: Follow the colour scheme the person chose (System, Light or Dark)
    Also: dark mode, light mode, theme choice, colour scheme setting, appearance
    Use: ColourSchemeChoice, ColourSchemePreference
    User: src/shell/appearance_options/appearance_options_page.py
    Status: stable
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum

from Sagittarius_Elite_Warrior.src.support.ui_kit.state.state_scope import (
    StateData,
    StateScope,
)

_SCOPE_KEY = "colour_scheme"
_CHOICE_KEY = "choice"


class ColourSchemeChoice(str, Enum):
    """What the person asked for; the values are what `ui_state` stores."""

    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


DEFAULT_CHOICE = ColourSchemeChoice.SYSTEM


def _parse(value: object) -> ColourSchemeChoice | None:
    try:
        return ColourSchemeChoice(value)
    except ValueError:
        return None


class ColourSchemePreference:
    """@brief The chosen colour scheme; tells its listeners when it changes."""

    def __init__(self, on_changed: Callable[[], None] | None = None) -> None:
        """@param on_changed Called after a change, so the owner can mark this dirty with the
        state coordinator (the bootstrapper wires it with `set_on_changed`)."""
        self._choice = DEFAULT_CHOICE
        self._on_changed = on_changed
        self._listeners: list[Callable[[ColourSchemeChoice], None]] = []

    def set_on_changed(self, on_changed: Callable[[], None]) -> None:
        self._on_changed = on_changed

    @property
    def choice(self) -> ColourSchemeChoice:
        return self._choice

    def set_choice(self, choice: ColourSchemeChoice) -> bool:
        """Chooses `choice`; `False` (and nothing changes) when it is the one already chosen."""
        if choice == self._choice:
            return False
        self._choice = choice
        for listener in tuple(self._listeners):
            listener(choice)
        if self._on_changed is not None:
            self._on_changed()
        return True

    def subscribe(
        self, listener: Callable[[ColourSchemeChoice], None]
    ) -> Callable[[], None]:
        """Calls `listener(choice)` after each change; returns the call that stops it."""
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    # -- IStateContributor (structural, no base class) ------------------- #

    @property
    def state_scope(self) -> StateScope:
        return StateScope(key=_SCOPE_KEY)

    def capture_state(self) -> StateData:
        return {_CHOICE_KEY: self._choice.value}

    def restore_state(self, data: StateData) -> None:
        """A remembered value this build does not know degrades to System, quietly: a restore
        announces nothing (`EPIC-010`), so no listener is called."""
        self._choice = _parse(data.get(_CHOICE_KEY)) or DEFAULT_CHOICE
