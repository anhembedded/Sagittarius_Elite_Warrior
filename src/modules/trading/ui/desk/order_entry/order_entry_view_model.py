"""`EPIC-028H` — the order panel's state: the chosen order type, what each
side typed, what the exchange said about the symbol, and whether an order is
being placed.

@details Plain Python state behind one `changed` signal: the panel repaints
from `figures()` and `entry()` on every change, so no field needs a signal
of its own. What the user typed is kept parsed; an unreadable field is
`None`, which `order_entry_rules` reports as "Enter a price" rather than
treating it as zero.

`EPIC-028I`: `options` holds time in force, reduce-only, TP/SL and the
Futures chips (`OrderOptionsViewModel`); the figures see a side's entry with
those options folded in, and every change there repaints the panel too.

`BOT-152`: the class holds the signals and the reads. What the user does to the
panel is `intents` (`OrderEntryUserIntents`) and what the presenter tells it is
`presenter_side()` (`OrderEntryPresenterWriter`), both over one shared
`OrderEntryState`, so the view cannot call the presenter's writes.

`EPIC-028O`: a side sized by quote (a Spot market buy) keeps a typed total
instead of a quantity, and its slider moves the total; a stop-limit side keeps
a stop price; the best-price button asks the presenter for the book through
`bestPriceRequested`, because reading the book is a network call.
"""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    DeskProfile,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_presenter_writer import (
    OrderEntryPresenterWriter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
    OrderEntryContext,
    SideFigures,
    SideInput,
    percent_of_max,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_state import (
    OrderEntryState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_user_intents import (
    OrderEntryUserIntents,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_options_view_model import (
    OrderOptionsViewModel,
)


class OrderEntryViewModel(QObject):
    """@brief The order panel's signals and reads, one instance per panel."""

    changed = Signal()
    #: A side's submit button was pressed; carries `EntrySide.value`.
    submitRequested = Signal(str)
    #: `EPIC-028O` — a side's best-price button was pressed; carries
    #: `EntrySide.value`. The presenter reads the book and answers with
    #: `OrderEntryPresenterWriter.set_price_value`.
    bestPriceRequested = Signal(str)
    #: `EPIC-033R` — New order… (F9) asks the panel to put the keyboard focus
    #: on its first field.
    focusRequested = Signal()

    def __init__(self, profile: DeskProfile, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = OrderEntryState(profile, profile.order_types[0])
        #: `EPIC-028I` — how this panel's orders are sent.
        self.options = OrderOptionsViewModel(self)
        self.options.changed.connect(self.changed)
        #: `BOT-152` — what the user does to the panel.
        self.intents = OrderEntryUserIntents(
            self._state,
            figures=self.figures,
            changed=self.changed,
            submit_requested=self.submitRequested,
            best_price_requested=self.bestPriceRequested,
            focus_requested=self.focusRequested,
        )
        self._presenter_side = OrderEntryPresenterWriter(
            self._state, self.options, self.changed
        )

    def presenter_side(self) -> OrderEntryPresenterWriter:
        """@return What the presenter tells the panel. Held by presenters and
        their helpers only; a view has no use for it."""
        return self._presenter_side

    @property
    def profile(self) -> DeskProfile:
        return self._state.profile

    @property
    def order_symbol(self) -> str:
        return self._state.symbol

    @property
    def order_type(self) -> OrderType:
        return self._state.order_type

    @property
    def context(self) -> OrderEntryContext | None:
        return self._state.context

    @property
    def last_price(self) -> Decimal | None:
        return self._state.last_price

    @property
    def busy(self) -> bool:
        return self._state.busy

    @property
    def can_take_order(self) -> bool:
        """Whether the fields take input: the symbol's terms are read and no
        order is in flight."""
        return not self._state.busy and self._state.context is not None

    @property
    def message(self) -> str:
        return self._state.message

    @property
    def message_is_error(self) -> bool:
        return self._state.message_is_error

    def entry(self, side: EntrySide) -> SideInput:
        return self._state.entries[side]

    def figures(self, side: EntrySide) -> SideFigures | None:
        """@return The side's figures, or `None` until the symbol's terms
        have been read."""
        state = self._state
        if state.context is None:
            return None
        return state.profile.figures(
            side,
            state.order_type,
            self.options.apply_to(side, state.entries[side]),
            state.context,
            state.last_price,
        )

    def percent(self, side: EntrySide) -> int:
        figures = self.figures(side)
        entry = self._state.entries[side]
        if figures is not None and figures.sized_by_quote:
            return percent_of_max(entry.total, figures.max_total)
        maximum = figures.max_quantity if figures is not None else None
        return percent_of_max(entry.quantity, maximum)
