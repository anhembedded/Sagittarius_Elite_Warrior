"""`BOT-152` — what the user does to the order panel: typing, the slider, the
buttons.

@details The half of the view model the view calls to change state. Apart from
the presenter's writes (`OrderEntryPresenterWriter`), which a view does not
ask for, and from the reads the view repaints from (`OrderEntryViewModel`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from PySide6.QtCore import SignalInstance
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.amount_text import (
    parse_amount,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    QUOTE_STEP,
    EntrySide,
    SideFigures,
    SideInput,
    quantity_at_percent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_state import (
    OrderEntryState,
)


class OrderEntryUserIntents:
    """@brief The user's side of the order panel, one instance per panel."""

    def __init__(
        self,
        state: OrderEntryState,
        *,
        figures: Callable[[EntrySide], SideFigures | None],
        changed: SignalInstance,
        submit_requested: SignalInstance,
        best_price_requested: SignalInstance,
        focus_requested: SignalInstance,
    ) -> None:
        self._state = state
        self._figures = figures
        self._changed = changed
        self._submit_requested = submit_requested
        self._best_price_requested = best_price_requested
        self._focus_requested = focus_requested

    def set_order_type(self, order_type: OrderType) -> None:
        state = self._state
        if order_type not in state.profile.order_types:
            raise ValueError(f"{order_type} is not offered on this desk")
        if order_type is not state.order_type:
            state.order_type = order_type
            self._changed.emit()

    def set_price(self, side: EntrySide, text: str) -> None:
        self._store(side, replace(self._state.entries[side], price=parse_amount(text)))

    def set_quantity(self, side: EntrySide, text: str) -> None:
        self._store(
            side, replace(self._state.entries[side], quantity=parse_amount(text))
        )

    def set_stop_price(self, side: EntrySide, text: str) -> None:
        self._store(
            side, replace(self._state.entries[side], stop_price=parse_amount(text))
        )

    def set_total(self, side: EntrySide, text: str) -> None:
        self._store(side, replace(self._state.entries[side], total=parse_amount(text)))

    def set_percent(self, side: EntrySide, percent: int) -> None:
        """Sets the amount (or, on a side sized by quote, the total) to
        `percent` of the side's maximum. Does nothing while the maximum is
        unknown."""
        state = self._state
        figures = self._figures(side)
        if figures is not None and figures.sized_by_quote:
            if figures.max_total is not None:
                total = quantity_at_percent(percent, figures.max_total, QUOTE_STEP)
                self._store(side, replace(state.entries[side], total=total))
            return
        if figures is None or figures.max_quantity is None or state.context is None:
            return
        step = state.context.terms.rules.step_size_for(state.order_type)
        quantity = quantity_at_percent(percent, figures.max_quantity, step)
        self._store(side, replace(state.entries[side], quantity=quantity))

    def use_last_price(self, side: EntrySide) -> None:
        state = self._state
        if state.last_price is not None:
            self._store(side, replace(state.entries[side], price=state.last_price))

    def use_best_price(self, side: EntrySide) -> None:
        self._best_price_requested.emit(side.value)

    def request_submit(self, side: EntrySide) -> None:
        self._submit_requested.emit(side.value)

    def request_focus(self) -> None:
        """New order… (`EPIC-033R`): places nothing, only asks for the focus."""
        self._focus_requested.emit()

    def _store(self, side: EntrySide, updated: SideInput) -> None:
        if self._state.store(side, updated):
            self._changed.emit()
