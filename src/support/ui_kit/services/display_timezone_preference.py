"""`BOT-205` — the display time zone the person chose, one for the whole application.

A display zone is a property of the person's clock, not of a screen: the Backtest report and
a bot's chart show the same moment, and two answers to "what time is it here" on two screens
is a misreading waiting to happen. The setting is therefore one object every screen follows
(`SymbolPreferences` is the same shape), remembered across sessions through `ui_state`.

It holds only the choice ("UTC", "SYSTEM" or an IANA key); turning a moment into that zone's
time is `display_timezone_service` alone.

Capability: Follow the display time zone the person chose
    Also: timezone choice, time zone setting, shared timezone, display zone
    Use: DisplayTimezonePreference, find_display_timezone_preference
    User: src/modules/bots/ui/bots_screen/bot_chart_host.py
    Status: stable
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_service import (
    DEFAULT_TIMEZONE,
    get_supported_timezones,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.state_scope import (
    StateData,
    StateScope,
)

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

_SCOPE_KEY = "display_timezone"
_ZONE_KEY = "zone"


def _is_offered(zone: object) -> bool:
    return isinstance(zone, str) and any(
        option["id"] == zone for option in get_supported_timezones()
    )


class DisplayTimezonePreference:
    """@brief The chosen display zone; tells its listeners when it changes."""

    def __init__(self, on_changed: Callable[[], None] | None = None) -> None:
        """@param on_changed Called after a change, so the owner can mark this dirty with the
        state coordinator (the bootstrapper wires it with `set_on_changed`)."""
        self._zone = DEFAULT_TIMEZONE
        #: Whether a restore found a zone of this setting's own.
        self._remembered = False
        self._on_changed = on_changed
        self._listeners: list[Callable[[str], None]] = []

    def set_on_changed(self, on_changed: Callable[[], None]) -> None:
        self._on_changed = on_changed

    @property
    def zone(self) -> str:
        return self._zone

    def set_zone(self, zone: str) -> bool:
        """Chooses `zone`; `False` (and nothing changes) for a zone the pickers do not offer
        or the one already chosen."""
        if zone == self._zone or not _is_offered(zone):
            return False
        self._zone = zone
        for listener in tuple(self._listeners):
            listener(zone)
        if self._on_changed is not None:
            self._on_changed()
        return True

    def subscribe(self, listener: Callable[[str], None]) -> Callable[[], None]:
        """Calls `listener(zone)` after each change; returns the call that stops it."""
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
        return {_ZONE_KEY: self._zone}

    def restore_state(self, data: StateData) -> None:
        """A remembered zone that is no longer offered degrades to the default, quietly: a
        restore announces nothing (`EPIC-010`), so no listener is called."""
        zone = data.get(_ZONE_KEY)
        self._remembered = _is_offered(zone)
        self._zone = (
            zone if _is_offered(zone) and isinstance(zone, str) else DEFAULT_TIMEZONE
        )

    def adopt_earlier_zone(self, zone: object) -> None:
        """Starts from `zone`, the one a screen remembered before this setting existed, when
        this setting has no value of its own yet; remembered from now on. Nothing else changes: a
        zone no picker offers, or a setting that already has a value, is left as it is."""
        if self._remembered or not _is_offered(zone) or not isinstance(zone, str):
            return
        self._zone = zone
        self._remembered = True
        if self._on_changed is not None:
            self._on_changed()


def find_display_timezone_preference(
    container: IContainer,
) -> DisplayTimezonePreference | None:
    """The registered shared setting, or `None` when the container holds none (a screen then
    keeps its own, unremembered one and still works) — `find_symbol_preferences`' shape."""
    registrations = container.registrations()
    if not isinstance(registrations, Mapping):
        return None
    if DisplayTimezonePreference not in registrations:
        return None
    resolved = container.resolve(DisplayTimezonePreference)
    return resolved if isinstance(resolved, DisplayTimezonePreference) else None
