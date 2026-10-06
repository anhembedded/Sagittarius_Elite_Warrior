"""Which venue the Trade mode trades (`EPIC-033I`): Trade → Venue › Futures, Spot.

The venue is a value of the mode (HLD §11.2.3), so one object holds it, as
`MarketChoice` holds the Market mode's market: it performs the venue
commands, keeps their checks in step, remembers the choice through the UI
state store (`IStateContributor`, structurally) and tells the presenter when
it changed. The actions are one exclusive `QActionGroup` in the window
(`CommandContribution.exclusive_group`).

Only the venues enabled in this run are offered; a remembered venue that is
no longer enabled gives way to the first one that is.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from functools import partial

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.state_scope import (
    StateData,
    StateScope,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.ui_state_coordinator import (
    UiStateCoordinator,
)

from .trade_commands import venue_choice_id

logger = logging.getLogger("App.Trading.Trade")

#: The remembered slice: `{"venue": TradingVenue.value}`.
_STATE_VENUE = "venue"


class _Checked(QObject):
    """Whether one venue's command is the checked one."""

    checked = Signal(bool)


class VenueChoice(QObject):
    """@brief The mode's venue: chosen, checked, remembered."""

    #: The new venue, after the person chose another one.
    changed = Signal(object)

    def __init__(
        self,
        venues: Sequence[TradingVenue],
        state: UiStateCoordinator | None,
        parent: QObject | None = None,
    ) -> None:
        """@param venues The venues enabled in this run, in menu order."""
        super().__init__(parent)
        self._venues = tuple(venues)
        self._state = state
        self._current: TradingVenue | None = self._venues[0] if self._venues else None
        self._checks = {venue: _Checked(self) for venue in self._venues}
        if state is not None:
            state.restore_into(self)

    @property
    def current(self) -> TradingVenue | None:
        """The venue traded; `None` when no venue is enabled."""
        return self._current

    @property
    def venues(self) -> tuple[TradingVenue, ...]:
        return self._venues

    def bind_commands(self, binder: ICommandBinder) -> None:
        for venue, check in self._checks.items():
            binder.bind(
                venue_choice_id(venue),
                partial(self._on_chosen, venue),
                checked=check.checked,
            )
        self._show_checked()

    def _on_chosen(self, venue: TradingVenue, _checked: bool) -> None:
        """The person checked `venue`; the same venue again changes nothing.
        The exclusive group never unchecks the checked action."""
        if venue is self._current:
            return
        logger.info(
            "[trade] venue %s -> %s",
            self._current.value if self._current is not None else "none",
            venue.value,
        )
        self._current = venue
        if self._state is not None:
            self._state.mark_dirty(self)
        self.changed.emit(venue)

    def _show_checked(self) -> None:
        for venue, check in self._checks.items():
            check.checked.emit(venue is self._current)

    # -- remembered state (`IStateContributor`, structural) --------------------

    @property
    def state_scope(self) -> StateScope:
        return StateScope(key="trade")

    def capture_state(self) -> StateData:
        return {_STATE_VENUE: self._current.value if self._current else ""}

    def restore_state(self, data: StateData) -> None:
        """Takes a remembered venue the mode still offers; anything else
        keeps the first. Tells nobody: nothing is shown yet."""
        value = data.get(_STATE_VENUE)
        self._current = next(
            (venue for venue in self._venues if venue.value == value), self._current
        )
