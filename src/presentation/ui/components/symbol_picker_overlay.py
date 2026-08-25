"""
@brief `SymbolPickerOverlay` — "choose a trading symbol", the one shape two
screens both needed.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QWidget
from sagittarius_engine.extensions.pyside_mvc.widgets import PickerItem, PickerOverlay

_TITLE = "CHỌN SYMBOL"
_SEARCH_PLACEHOLDER = "Tìm symbol (vd: BTC)"
_EMPTY_TEXT = "Đang tải danh sách symbol từ sàn..."

#: Symbols are short (`BTCUSDT`), so three to a row reads as a keypad rather
#: than a list. Matches what both screens already rendered.
_COLUMNS = 3


class SymbolPickerOverlay(PickerOverlay):
    """
    @brief A modal grid of tradable symbols with a search box.

    @details
    Engine's `PickerOverlay` supplies the mechanism — searchable grid of
    `SelectableCard`s, `selection_changed`. This names it, in this app's
    language, and adds the one behaviour a generic picker cannot have: the
    option list is fetched from the exchange, so it is refreshed on every
    open rather than captured once at construction.

    **Choosing closes the dialog.** `PickerOverlay` deliberately does not do
    that itself — one of the app's six pickers (time range) must stay open on
    "custom" — so each consumer says. For a symbol there is nothing to stay
    open for.

    Both screens that pick a symbol reach this: Data Management, and
    Backtest's own `BacktestSymbolPickerDialog`, which `EPIC-007F` migrates.
    Until it does, two dialogs still render this shape; this is the one that
    should survive.
    """

    def __init__(
        self,
        get_options: Callable[[], list[str]],
        on_symbol_chosen: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            _TITLE,
            searchable=True,
            search_placeholder=_SEARCH_PLACEHOLDER,
            columns=_COLUMNS,
            empty_text=_EMPTY_TEXT,
            parent=parent,
        )
        self.setObjectName("symbolPickerModal")
        self._get_options = get_options
        self.selection_changed.connect(on_symbol_chosen)
        self.selection_changed.connect(lambda _symbol: self.accept())

    def showEvent(self, event) -> None:
        """@brief Refetches the symbol list every time the dialog opens.

        @details The exchange's list arrives asynchronously and can be empty
        on the first open — which is what `_EMPTY_TEXT` is for. Reading it
        here rather than in `__init__` is why the dialog can be constructed
        once and reused, as both screens do."""
        self.set_items([PickerItem(symbol, symbol) for symbol in self._get_options()])
        super().showEvent(event)
