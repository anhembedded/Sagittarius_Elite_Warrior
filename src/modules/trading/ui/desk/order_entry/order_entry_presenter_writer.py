"""`BOT-152` — what the presenter tells the order panel: a new symbol, its
terms, the last price, the outcome of an order.

@details The half of the view model only presenters and their helpers hold
(`OrderEntryViewModel.presenter_side`); the view is given no way to call it.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from PySide6.QtCore import SignalInstance
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
    OrderEntryContext,
    SideInput,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_state import (
    OrderEntryState,
    blank_entries,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_options_view_model import (
    OrderOptionsViewModel,
)


class OrderEntryPresenterWriter:
    """@brief The presenter's side of the order panel, one instance per panel."""

    def __init__(
        self,
        state: OrderEntryState,
        options: OrderOptionsViewModel,
        changed: SignalInstance,
    ) -> None:
        self._state = state
        self._options = options
        self._changed = changed

    def begin_symbol(self, symbol: str) -> None:
        """A new symbol: its terms are unknown until read, and what was typed
        for the previous one no longer applies."""
        state = self._state
        state.symbol = symbol
        state.context = None
        state.last_price = None
        state.entries = blank_entries()
        self._options.clear_levels()
        self._options.show_setting(None)
        state.loading = True
        self._set_message(f"Loading {symbol}...", is_error=False)

    def set_context(self, context: OrderEntryContext) -> None:
        """The symbol's terms, read. Clears the "Loading" line of a new
        symbol only: a re-read after an order or a leverage change keeps
        what the panel said about it (`EPIC-028I`)."""
        state = self._state
        state.context = context
        if state.loading:
            state.loading = False
            self._set_message("", is_error=False)
        else:
            self._changed.emit()

    def set_last_price(self, price: Decimal | None) -> None:
        if price != self._state.last_price:
            self._state.last_price = price
            self._changed.emit()

    def set_price_value(self, side: EntrySide, price: Decimal) -> None:
        """The best price the presenter read for `side`."""
        self._store(side, replace(self._state.entries[side], price=price))

    def set_busy(self, busy: bool, message: str) -> None:
        self._state.busy = busy
        self._set_message(message, is_error=False)

    def show_error(self, message: str) -> None:
        self._state.busy = False
        self._set_message(message, is_error=True)

    def show_result(self, message: str, *, is_error: bool) -> None:
        self._state.busy = False
        self._set_message(message, is_error=is_error)

    def clear_amount(self, side: EntrySide) -> None:
        self._store(side, replace(self._state.entries[side], quantity=None, total=None))

    def _store(self, side: EntrySide, updated: SideInput) -> None:
        if self._state.store(side, updated):
            self._changed.emit()

    def _set_message(self, message: str, *, is_error: bool) -> None:
        self._state.message = message
        self._state.message_is_error = is_error
        self._changed.emit()
