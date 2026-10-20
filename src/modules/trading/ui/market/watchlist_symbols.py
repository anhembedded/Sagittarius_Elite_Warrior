"""The symbols the Market mode's Watchlist tracks (`EPIC-033V`).

They start as the configured symbols (`DEFAULT_SYMBOLS`, with the floor of
`market_dependencies.py`); the person adds a symbol with View → Add to
Watchlist… and removes one with View → Remove from Watchlist, and the list is
remembered through the UI state store (`IStateContributor`, structurally) as
`MarketChoice` remembers the market. One list for both markets, as
`EPIC-033Q` recorded.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.state_scope import (
    StateData,
    StateScope,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.ui_state_coordinator import (
    UiStateCoordinator,
)

logger = logging.getLogger("App.Trading.Market")

#: The remembered slice: `{"symbols": [str, ...]}`.
_STATE_SYMBOLS = "symbols"


class WatchlistSymbols(QObject):
    """@brief The tracked symbols: listed, changed, remembered."""

    #: The tracked symbols after an add or a remove, in tracking order.
    changed = Signal(tuple)

    def __init__(
        self,
        configured: Sequence[str],
        state: UiStateCoordinator | None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._symbols: list[str] = list(configured)
        if state is not None:
            state.restore_into(self)

    @property
    def entries(self) -> tuple[str, ...]:
        return tuple(self._symbols)

    def add(self, symbol: str) -> bool:
        """Tracks `symbol`; `False` when it already is (or is blank)."""
        symbol = symbol.strip().upper()
        if not symbol or symbol in self._symbols:
            return False
        self._symbols.append(symbol)
        self._changed(f"added {symbol}")
        return True

    def remove(self, symbol: str) -> bool:
        """Stops tracking `symbol`; `False` when it was not tracked."""
        if symbol not in self._symbols:
            return False
        self._symbols.remove(symbol)
        self._changed(f"removed {symbol}")
        return True

    def _changed(self, what: str) -> None:
        logger.info("[market] watchlist %s -> %d symbols", what, len(self._symbols))
        if self._state is not None:
            self._state.mark_dirty(self)
        self.changed.emit(self.entries)

    # -- remembered state (`IStateContributor`, structural) --------------------

    @property
    def state_scope(self) -> StateScope:
        return StateScope(key="market_watchlist")

    def capture_state(self) -> StateData:
        return {_STATE_SYMBOLS: list(self._symbols)}

    def restore_state(self, data: StateData) -> None:
        """Takes a remembered list of symbols; anything else keeps the
        configured ones. An empty remembered list stays empty: the person
        removed them all. Tells nobody: nothing is open yet."""
        remembered = data.get(_STATE_SYMBOLS)
        if not isinstance(remembered, list):
            return
        cleaned: list[str] = []
        for value in remembered:
            if not isinstance(value, str):
                continue
            symbol = value.strip().upper()
            if symbol and symbol not in cleaned:
                cleaned.append(symbol)
        self._symbols = cleaned
