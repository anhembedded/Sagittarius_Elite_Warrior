"""Which market the Market mode shows (`EPIC-033Q`): View → Spot market or Futures market.

The market is a value of the mode, not of each chart (HLD §11.2.3), so one
object holds it: it performs the two commands, keeps their checks in step,
remembers the choice through the UI state store (`IStateContributor`,
structurally) and tells the presenter when it changed. The two actions are
one exclusive `QActionGroup` in the window (`CommandContribution`'s
`exclusive_group`).
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
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

from .market_commands import SHOW_FUTURES, SHOW_SPOT
from .market_dependencies import DEFAULT_MARKET, MARKETS

logger = logging.getLogger("App.Trading.Market")

#: The remembered slice: `{"market": MarketType.value}`.
_STATE_MARKET = "market"
MARKET_TEXT = {MarketType.SPOT: "Spot", MarketType.FUTURES_USD_M: "Futures"}


class MarketChoice(QObject):
    """@brief The mode's market: chosen, checked, remembered."""

    #: The new market, after the person chose another one.
    changed = Signal(object)
    #: Whether View → Spot market, and View → Futures market, is the checked market.
    spotChecked = Signal(bool)
    futuresChecked = Signal(bool)

    def __init__(
        self, state: UiStateCoordinator | None, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._market = DEFAULT_MARKET
        if state is not None:
            state.restore_into(self)

    @property
    def current(self) -> MarketType:
        return self._market

    def bind_commands(self, binder: ICommandBinder) -> None:
        binder.bind(
            SHOW_SPOT,
            lambda _checked: self._on_chosen(MarketType.SPOT),
            checked=self.spotChecked,
        )
        binder.bind(
            SHOW_FUTURES,
            lambda _checked: self._on_chosen(MarketType.FUTURES_USD_M),
            checked=self.futuresChecked,
        )
        self._show_checked()

    def _on_chosen(self, market: MarketType) -> None:
        """The person checked `market`; the same market again changes
        nothing. The exclusive group never unchecks the checked action, so
        the action's checked state needs no reading here."""
        if market is self._market:
            return
        logger.info("[market] market %s -> %s", self._market.name, market.name)
        self._market = market
        if self._state is not None:
            self._state.mark_dirty(self)
        self.changed.emit(market)

    def _show_checked(self) -> None:
        self.spotChecked.emit(self._market is MarketType.SPOT)
        self.futuresChecked.emit(self._market is MarketType.FUTURES_USD_M)

    # -- remembered state (`IStateContributor`, structural) --------------------

    @property
    def state_scope(self) -> StateScope:
        return StateScope(key="market")

    def capture_state(self) -> StateData:
        return {_STATE_MARKET: self._market.value}

    def restore_state(self, data: StateData) -> None:
        """Takes a remembered market the mode still offers; anything else
        keeps the default. Tells nobody: nothing is open yet."""
        value = data.get(_STATE_MARKET)
        self._market = next((m for m in MARKETS if m.value == value), DEFAULT_MARKET)
