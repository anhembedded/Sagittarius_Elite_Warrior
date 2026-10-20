"""View → Symbol…, Add to Watchlist… and Remove from Watchlist (`EPIC-033V`).

Presenter-owned (`async-ui-action-rule.md` §2), never registered. This object
decides what a choice in the shared symbol picker means for the Market mode
(a chart for Symbol…, a Watchlist row for Add to Watchlist…) and when Remove
may run (a Watchlist row selected); the picker itself, the catalog read and
the remembered Watchlist are the objects it is handed.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import INotifier
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)

from .market_commands import ADD_TO_WATCHLIST, CHOOSE_SYMBOL, REMOVE_FROM_WATCHLIST
from .market_dependencies import MarketDependencies
from .market_symbol_picker import MarketSymbolPicker
from .market_view import MarketView
from .watchlist_symbols import WatchlistSymbols

logger = logging.getLogger("App.Trading.Market")


class SymbolCommands(QObject):
    """@brief The commands that choose, track and untrack a symbol."""

    #: Whether Remove from Watchlist may run: a row is selected.
    removeEnabledChanged = Signal(bool)

    def __init__(
        self,
        view: MarketView,
        picker: MarketSymbolPicker,
        tracked: WatchlistSymbols,
        open_chart: Callable[[str], None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._view = view
        self._picker = picker
        self._tracked = tracked
        self._open_chart = open_chart
        view.watchlist_selected.connect(lambda _symbol: self.refresh())

    def bind_commands(self, binder: ICommandBinder) -> None:
        binder.bind(CHOOSE_SYMBOL, lambda _checked: self.choose())
        binder.bind(ADD_TO_WATCHLIST, lambda _checked: self.add())
        binder.bind(
            REMOVE_FROM_WATCHLIST,
            lambda _checked: self.remove(),
            enabled=self.removeEnabledChanged,
            initially_enabled=bool(self._view.selected_watchlist_symbol),
        )

    def refresh(self) -> None:
        self.removeEnabledChanged.emit(bool(self._view.selected_watchlist_symbol))

    def choose(self) -> None:
        """Opens the picker; the chosen symbol's chart opens, or comes
        forward when it is open."""
        self._picker.open(
            self._view.window(), self._view.current_symbol, self._open_chart
        )

    def add(self) -> None:
        """Opens the picker; the chosen symbol joins the Watchlist."""
        self._picker.open(self._view.window(), "", self._track)

    def remove(self) -> None:
        """Stops tracking the selected row; an open chart of it stays."""
        symbol = self._view.selected_watchlist_symbol
        if symbol and self._tracked.remove(symbol):
            self._view.log.append(f"{symbol} is no longer in the Watchlist.")

    def _track(self, symbol: str) -> None:
        if self._tracked.add(symbol):
            self._view.log.append(f"{symbol} added to the Watchlist.")
        else:
            self._view.log.append(f"{symbol} is already in the Watchlist.")
        logger.info("[market] add to watchlist asked for %s", symbol)


def symbol_commands_for(
    view: MarketView,
    dependencies: MarketDependencies,
    notifier: INotifier,
    market: Callable[[], MarketType],
    tracked: WatchlistSymbols,
    open_chart: Callable[[str], None],
    parent: QObject,
) -> SymbolCommands:
    """The commands over a picker on the dependencies' catalog and
    preferences, listing the symbols of `market()`."""
    picker = MarketSymbolPicker(
        dependencies.catalog,
        dependencies.thread_manager,
        dependencies.preferences,
        notifier,
        market,
        parent,
    )
    return SymbolCommands(view, picker, tracked, open_chart, parent)
