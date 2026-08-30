"""`BacktestSymbolPickerSource` — Backtest's `ISymbolPickerSource` implementer.

@details The one adapter file translating between Backtest's real data (the
screen ViewModel's `symbolOptions`/`selectedSymbol`, the shared
`SymbolPreferences` store) and the standalone picker's app-neutral contract.
Kept apart from `symbol_picker_dialog.py` (the `QWidget` composition root that
wires this adapter's VM into a `QDialog`) per `architecture-rule.md` §5: a
Port implementer and the widget wiring that constructs it are different
abstraction levels and do not share a file.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.presentation.ui.components.symbol_picker import (
    SymbolPreferences,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.interfaces.i_symbol_picker_source import (
    ISymbolPickerSource,
)

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel


class BacktestSymbolPickerSource(ISymbolPickerSource):
    """Reads Backtest's live symbol data; writes favourite toggles back.

    @details `set_favourite()` is the one write path `ISymbolPickerSource`
    declares, and `SymbolPreferences` only exposes `toggle_favourite()` (it
    flips its own internal state and returns the new value — there is no
    `set_favourite(symbol, value)` on that store). Calling `toggle_favourite`
    unconditionally here would double-flip whenever the picker's own idea of
    the current state already agrees with `favourite` (it cannot otherwise,
    since `SymbolPickerVM.toggleFavourite()` always flips its cached entry
    before calling this), so this guards on `is_favourite()` disagreeing
    first. Recording "recently used" is deliberately NOT here:
    `ISymbolPickerSource` has no write path for recents (`get_recents()` is
    read-only, host-driven per `SymbolPicker/NOTES.md`) — that call belongs
    to whoever handles the picker's `symbolChosen`, not to this contract.
    """

    def __init__(
        self, view_model: BackTestViewModel, preferences: SymbolPreferences
    ) -> None:
        self._view_model = view_model
        self._preferences = preferences

    def set_preferences(self, preferences: SymbolPreferences) -> None:
        """Swaps the backing store — `BackTestModalsHost.set_symbol_preferences`'s
        seam, forwarded here with nothing to rebind: unlike the old
        `SymbolPreferences.bind_picker`, nothing in this adapter connects a
        Qt signal to the store, so there is no stale connection to undo."""
        self._preferences = preferences

    def get_symbols(self) -> Sequence[str]:
        return self._view_model.symbolOptions

    def get_favourites(self) -> Sequence[str]:
        return self._preferences.favourites

    def get_recents(self) -> Sequence[str]:
        return self._preferences.recents

    def get_current(self) -> str:
        return self._view_model.selectedSymbol

    def set_favourite(self, symbol: str, favourite: bool) -> None:
        if self._preferences.is_favourite(symbol) != favourite:
            self._preferences.toggle_favourite(symbol)
