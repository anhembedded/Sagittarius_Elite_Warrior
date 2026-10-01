"""`EPIC-028H` — the order panel's state: the chosen order type, what each
side typed, what the exchange said about the symbol, and whether an order is
being placed.

@details Plain Python state behind one `changed` signal: the panel repaints
from `figures()` and `entry()` on every change, so no field needs a signal
of its own. What the user typed is kept parsed; an unreadable field is
`None`, which `order_entry_rules` reports as "Enter a price" rather than
treating it as zero.

`EPIC-028O`: a side sized by quote (a Spot market buy) keeps a typed total
instead of a quantity, and its slider moves the total; a stop-limit side keeps
a stop price; the best-price button asks the presenter for the book through
`bestPriceRequested`, because reading the book is a network call.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    DeskProfile,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    QUOTE_STEP,
    EntrySide,
    OrderEntryContext,
    SideFigures,
    SideInput,
    percent_of_max,
    quantity_at_percent,
)


def parse_amount(text: str) -> Decimal | None:
    """@return `text` as a finite, non-negative `Decimal`, or `None`.
    Thousands separators are accepted, because the panel shows them."""
    try:
        value = Decimal(text.replace(",", "").strip())
    except InvalidOperation:
        return None
    if not value.is_finite() or value < 0:
        return None
    return value


class OrderEntryViewModel(QObject):
    """@brief The order panel's state, one instance per panel."""

    changed = Signal()
    #: A side's submit button was pressed; carries `EntrySide.value`.
    submitRequested = Signal(str)
    #: `EPIC-028O` — a side's best-price button was pressed; carries
    #: `EntrySide.value`. The presenter reads the book and answers with
    #: `set_price_value`.
    bestPriceRequested = Signal(str)

    def __init__(self, profile: DeskProfile, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._profile = profile
        self._order_type = profile.order_types[0]
        self._symbol = ""
        self._context: OrderEntryContext | None = None
        self._last_price: Decimal | None = None
        self._entries = {side: SideInput() for side in EntrySide}
        self._busy = False
        self._message = ""
        self._message_is_error = False

    # -- read ---------------------------------------------------------- #

    @property
    def profile(self) -> DeskProfile:
        return self._profile

    @property
    def order_symbol(self) -> str:
        return self._symbol

    @property
    def order_type(self) -> OrderType:
        return self._order_type

    @property
    def context(self) -> OrderEntryContext | None:
        return self._context

    @property
    def last_price(self) -> Decimal | None:
        return self._last_price

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def message(self) -> str:
        return self._message

    @property
    def message_is_error(self) -> bool:
        return self._message_is_error

    def entry(self, side: EntrySide) -> SideInput:
        return self._entries[side]

    def figures(self, side: EntrySide) -> SideFigures | None:
        """@return The side's figures, or `None` until the symbol's terms
        have been read."""
        if self._context is None:
            return None
        return self._profile.figures(
            side,
            self._order_type,
            self._entries[side],
            self._context,
            self._last_price,
        )

    def percent(self, side: EntrySide) -> int:
        figures = self.figures(side)
        entry = self._entries[side]
        if figures is not None and figures.sized_by_quote:
            return percent_of_max(entry.total, figures.max_total)
        maximum = figures.max_quantity if figures is not None else None
        return percent_of_max(entry.quantity, maximum)

    # -- the user ------------------------------------------------------ #

    def set_order_type(self, order_type: OrderType) -> None:
        if order_type not in self._profile.order_types:
            raise ValueError(f"{order_type} is not offered on this desk")
        if order_type is not self._order_type:
            self._order_type = order_type
            self.changed.emit()

    def set_price(self, side: EntrySide, text: str) -> None:
        self._store(side, replace(self._entries[side], price=parse_amount(text)))

    def set_quantity(self, side: EntrySide, text: str) -> None:
        self._store(side, replace(self._entries[side], quantity=parse_amount(text)))

    def set_stop_price(self, side: EntrySide, text: str) -> None:
        self._store(side, replace(self._entries[side], stop_price=parse_amount(text)))

    def set_total(self, side: EntrySide, text: str) -> None:
        self._store(side, replace(self._entries[side], total=parse_amount(text)))

    def set_percent(self, side: EntrySide, percent: int) -> None:
        """Sets the amount (or, on a side sized by quote, the total) to
        `percent` of the side's maximum. Does nothing while the maximum is
        unknown."""
        figures = self.figures(side)
        if figures is not None and figures.sized_by_quote:
            if figures.max_total is not None:
                total = quantity_at_percent(percent, figures.max_total, QUOTE_STEP)
                self._store(side, replace(self._entries[side], total=total))
            return
        if figures is None or figures.max_quantity is None or self._context is None:
            return
        step = self._context.terms.rules.step_size_for(self._order_type)
        quantity = quantity_at_percent(percent, figures.max_quantity, step)
        self._store(side, replace(self._entries[side], quantity=quantity))

    def use_last_price(self, side: EntrySide) -> None:
        if self._last_price is not None:
            self._store(side, replace(self._entries[side], price=self._last_price))

    def use_best_price(self, side: EntrySide) -> None:
        self.bestPriceRequested.emit(side.value)

    def request_submit(self, side: EntrySide) -> None:
        self.submitRequested.emit(side.value)

    # -- the presenter ------------------------------------------------- #

    def begin_symbol(self, symbol: str) -> None:
        """A new symbol: its terms are unknown until read, and what was typed
        for the previous one no longer applies."""
        self._symbol = symbol
        self._context = None
        self._last_price = None
        self._entries = {side: SideInput() for side in EntrySide}
        self._set_message(f"Loading {symbol}...", is_error=False)

    def set_context(self, context: OrderEntryContext) -> None:
        self._context = context
        self._set_message("", is_error=False)

    def set_last_price(self, price: Decimal | None) -> None:
        if price != self._last_price:
            self._last_price = price
            self.changed.emit()

    def set_price_value(self, side: EntrySide, price: Decimal) -> None:
        """The best price the presenter read for `side`."""
        self._store(side, replace(self._entries[side], price=price))

    def set_busy(self, busy: bool, message: str) -> None:
        self._busy = busy
        self._set_message(message, is_error=False)

    def show_error(self, message: str) -> None:
        self._busy = False
        self._set_message(message, is_error=True)

    def show_result(self, message: str, *, is_error: bool) -> None:
        self._busy = False
        self._set_message(message, is_error=is_error)

    def clear_amount(self, side: EntrySide) -> None:
        self._store(side, replace(self._entries[side], quantity=None, total=None))

    def _store(self, side: EntrySide, updated: SideInput) -> None:
        if updated != self._entries[side]:
            self._entries[side] = updated
            self.changed.emit()

    def _set_message(self, message: str, *, is_error: bool) -> None:
        self._message = message
        self._message_is_error = is_error
        self.changed.emit()
