"""`EPIC-043D` — whether a price briefly takes the up or down tone when it ticks.

Off by default (`PRO-009` Q3): a flashing figure is the one motion in an otherwise still window,
and the person asks for it in Tools → Options → Appearance. It is a property of the person's
desktop, not of a screen, so one object holds it and everything that cares follows it
(`ColourSchemePreference` is the same shape), remembered across sessions through `ui_state`.
It holds only the choice; what a price does with it is the table's.

Capability: Follow whether a price flashes when it ticks (off by default)
    Also: tick flash, price flash, live price movement, flash on tick, price colour on tick
    Use: TickFlashPreference, find_tick_flash_preference
    User: src/shell/appearance_options/appearance_options_page.py
    Status: stable
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.support.ui_kit.state.state_scope import (
    StateData,
    StateScope,
)

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

_SCOPE_KEY = "tick_flash"
_ENABLED_KEY = "enabled"


class TickFlashPreference:
    """@brief Whether a ticking price flashes; tells its listeners when that changes."""

    def __init__(self, on_changed: Callable[[], None] | None = None) -> None:
        """@param on_changed Called after a change, so the owner can mark this dirty with the
        state coordinator (the bootstrapper wires it with `set_on_changed`)."""
        self._enabled = False
        self._on_changed = on_changed
        self._listeners: list[Callable[[bool], None]] = []

    def set_on_changed(self, on_changed: Callable[[], None]) -> None:
        self._on_changed = on_changed

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> bool:
        """Turns the flash on or off; `False` (and nothing changes) when it is already so."""
        if enabled == self._enabled:
            return False
        self._enabled = enabled
        for listener in tuple(self._listeners):
            listener(enabled)
        if self._on_changed is not None:
            self._on_changed()
        return True

    def subscribe(self, listener: Callable[[bool], None]) -> Callable[[], None]:
        """Calls `listener(enabled)` after each change; returns the call that stops it."""
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
        return {_ENABLED_KEY: self._enabled}

    def restore_state(self, data: StateData) -> None:
        """Only a remembered `True` turns it on: a value this build does not read keeps it off,
        quietly. A restore announces nothing (`EPIC-010`), so no listener is called."""
        self._enabled = data.get(_ENABLED_KEY) is True


def find_tick_flash_preference(container: IContainer) -> TickFlashPreference | None:
    """The registered preference, or `None` when the container holds none (a screen built in a
    test, or before the bootstrapper registered it): the flash then stays off. Never raises."""
    registrations = container.registrations()
    if not isinstance(registrations, Mapping):
        return None
    if TickFlashPreference not in registrations:
        return None
    resolved = container.resolve(TickFlashPreference)
    return resolved if isinstance(resolved, TickFlashPreference) else None
