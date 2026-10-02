"""`EPIC-028H` — one side of the order panel: price, amount, the % slider,
the figures and the submit button.

@details Both desks' layouts are built from this form: the Spot desk shows a
Buy form and a Sell form side by side, and the Futures desk (`EPIC-028I`)
one form with two buttons. The form reads everything from the view model and
writes every edit back to it; it keeps no state of its own beyond the text a
user is typing. A field is only rewritten when the model's value differs from
what the text already says, so typing is never interrupted mid-number.

`EPIC-028O`: a stop-price row shows only on a stop-limit; a side sized by
quote (a Spot market buy) shows a total field in place of the amount; the
BBO button fills the best price on the side's own side of the book (a buy
gets the best bid, a sell the best ask), so the order joins the queue and
never crosses the spread; it shows on the Limit tab only.

`EPIC-028I`: the side's TP/SL fields (`ProtectionFields`), and on a desk
with leverage its cost and the liquidation estimate, labelled as one.
"""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.amount_text import (
    NONE_TEXT,
    format_amount,
    parse_amount,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
    SideFigures,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_view_model import (
    OrderEntryViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.protection_fields import (
    ProtectionFields,
)

_NONE_TEXT = NONE_TEXT
_SLIDER_STEP = 25
_CENT = Decimal("0.01")


def order_type_joins_queue_now(order_type: OrderType) -> bool:
    """Whether an order of this type rests on the book as soon as it is
    placed, so the front of the queue (BBO) is a meaningful price for it."""
    return order_type is OrderType.LIMIT


_BEST_PRICE_TIP = {
    EntrySide.BUY: "Use the best bid: the order joins the front of the buy queue",
    EntrySide.SELL: "Use the best ask: the order joins the front of the sell queue",
}


class OrderSideForm(QWidget):  # base-exempt: a container, not a surface
    """@brief One side's fields, figures and submit button."""

    def __init__(
        self,
        view_model: OrderEntryViewModel,
        side: EntrySide,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._side = side
        name = side.value.capitalize()
        self.setObjectName(f"orderSide{name}")

        self._price = QLineEdit()
        self._price.setObjectName(f"txtPrice{name}")
        self._price.setPlaceholderText("Price")
        self._price.textEdited.connect(lambda text: view_model.set_price(side, text))
        self._last = QToolButton()
        self._last.setObjectName(f"btnLastPrice{name}")
        self._last.setText("Last")
        self._last.setToolTip("Use the last traded price")
        self._last.clicked.connect(lambda: view_model.use_last_price(side))
        self._best = QToolButton()
        self._best.setObjectName(f"btnBestPrice{name}")
        self._best.setText("BBO")
        self._best.setToolTip(_BEST_PRICE_TIP[side])
        self._best.clicked.connect(lambda: view_model.use_best_price(side))
        self._market_price = QLabel("Market price")
        self._price_unit = QLabel()

        self._stop = QLineEdit()
        self._stop.setObjectName(f"txtStopPrice{name}")
        self._stop.setPlaceholderText("Stop")
        self._stop.setToolTip("The order is placed once the last price reaches this")
        self._stop.textEdited.connect(
            lambda text: view_model.set_stop_price(side, text)
        )
        self._stop_unit = QLabel()

        self._quantity = QLineEdit()
        self._quantity.setObjectName(f"txtAmount{name}")
        self._quantity.setPlaceholderText("Amount")
        self._quantity.textEdited.connect(
            lambda text: view_model.set_quantity(side, text)
        )
        self._quantity_unit = QLabel()

        self._spend = QLineEdit()
        self._spend.setObjectName(f"txtTotal{name}")
        self._spend.setPlaceholderText("Total")
        self._spend.setToolTip("How much to spend; the exchange decides the amount")
        self._spend.textEdited.connect(lambda text: view_model.set_total(side, text))
        self._spend_unit = QLabel()

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setObjectName(f"sldPercent{name}")
        self._slider.setRange(0, 100)
        self._slider.setSingleStep(1)
        self._slider.setPageStep(_SLIDER_STEP)
        self._slider.setTickInterval(_SLIDER_STEP)
        self._slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._slider.valueChanged.connect(
            lambda percent: view_model.set_percent(side, percent)
        )

        self._available = QLabel(_NONE_TEXT)
        self._available.setObjectName(f"lblAvailable{name}")
        self._maximum = QLabel(_NONE_TEXT)
        self._maximum.setObjectName(f"lblMax{name}")
        self._total = QLabel(_NONE_TEXT)
        self._total.setObjectName(f"lblTotal{name}")
        self._fee = QLabel(_NONE_TEXT)
        self._fee.setObjectName(f"lblFee{name}")
        self._cost = QLabel(_NONE_TEXT)
        self._cost.setObjectName(f"lblCost{name}")
        self._liquidation = QLabel(_NONE_TEXT)
        self._liquidation.setObjectName(f"lblLiquidation{name}")
        self._liquidation.setToolTip(
            "An estimate for this order's position alone; the exchange's own "
            "figure also counts your other positions"
        )
        self._protection = ProtectionFields(view_model.options, side)
        self._problem = QLabel()
        self._problem.setObjectName(f"lblProblem{name}")
        self._problem.setWordWrap(True)
        self._submit = QPushButton()
        self._submit.setObjectName(f"btnSubmit{name}")
        self._submit.clicked.connect(lambda: view_model.request_submit(side))

        stop_row = QHBoxLayout()
        stop_row.addWidget(self._stop, 1)
        stop_row.addWidget(self._stop_unit)
        price_row = QHBoxLayout()
        price_row.addWidget(self._price, 1)
        price_row.addWidget(self._market_price, 1)
        price_row.addWidget(self._last)
        price_row.addWidget(self._best)
        price_row.addWidget(self._price_unit)
        quantity_row = QHBoxLayout()
        quantity_row.addWidget(self._quantity, 1)
        quantity_row.addWidget(self._quantity_unit)
        quantity_row.addWidget(self._spend, 1)
        quantity_row.addWidget(self._spend_unit)
        figures = QFormLayout()
        figures.addRow("Available", self._available)
        self._maximum_label = QLabel()
        figures.addRow(self._maximum_label, self._maximum)
        figures.addRow("Total", self._total)
        figures.addRow("Est. fee", self._fee)
        if view_model.profile.futures_controls:
            figures.addRow("Cost", self._cost)
            figures.addRow("Liq. price (est.)", self._liquidation)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(stop_row)
        layout.addLayout(price_row)
        layout.addLayout(quantity_row)
        layout.addWidget(self._protection)
        layout.addWidget(self._slider)
        layout.addLayout(figures)
        layout.addWidget(self._problem)
        layout.addWidget(self._submit)

        view_model.changed.connect(self.sync)
        self.sync()

    def sync(self) -> None:
        vm = self._vm
        side = self._side
        entry = vm.entry(side)
        figures = vm.figures(side)
        context = vm.context
        is_market = vm.order_type is OrderType.MARKET
        is_stop = vm.order_type is OrderType.STOP_LIMIT
        by_quote = figures is not None and figures.sized_by_quote
        base = context.base_asset if context else ""
        quote = context.quote_asset if context else vm.profile.quote_asset

        for widget in (self._stop, self._stop_unit):
            widget.setVisible(is_stop)
        self._price.setVisible(not is_market)
        self._last.setVisible(not is_market)
        # A stop-limit's limit price is where it rests once triggered, not
        # the queue it joins now, so BBO offers the wrong price there.
        self._best.setVisible(order_type_joins_queue_now(vm.order_type))
        self._market_price.setVisible(is_market)
        for widget in (self._quantity, self._quantity_unit):
            widget.setVisible(not by_quote)
        for widget in (self._spend, self._spend_unit):
            widget.setVisible(by_quote)
        self._stop_unit.setText(quote)
        self._price_unit.setText(quote)
        self._quantity_unit.setText(base)
        self._spend_unit.setText(quote)
        _show_value(self._stop, entry.stop_price)
        _show_value(self._price, entry.price)
        _show_value(self._quantity, entry.quantity)
        _show_value(self._spend, entry.total)
        self._slider.blockSignals(True)
        self._slider.setValue(vm.percent(side))
        self._slider.blockSignals(False)

        label = vm.profile.side_label(side)
        self._maximum_label.setText("Max total" if by_quote else f"Max {label.lower()}")
        self._available.setText(
            f"{format_amount(figures.available)} {figures.available_asset}"
            if figures is not None
            else _NONE_TEXT
        )
        self._maximum.setText(_maximum_text(figures, base, quote))
        self._total.setText(
            f"{format_amount(figures.total)} {quote}" if figures else _NONE_TEXT
        )
        self._fee.setText(
            f"{format_amount(figures.fee)} {quote}" if figures else _NONE_TEXT
        )
        self._cost.setText(
            f"{format_amount(figures.cost)} {quote}"
            if figures and figures.cost is not None
            else _NONE_TEXT
        )
        self._liquidation.setText(_liquidation_text(figures))
        self._problem.setText((figures.problem or "") if figures else "")
        self._submit.setText(f"{label} {base}".strip())
        ready = figures is not None and figures.can_submit
        self._submit.setEnabled(ready and not vm.busy)
        editable = (
            self._stop,
            self._price,
            self._last,
            self._best,
            self._quantity,
            self._spend,
            self._slider,
        )
        for field in editable:
            field.setEnabled(not vm.busy and figures is not None)


def _liquidation_text(figures: SideFigures | None) -> str:
    estimate = figures.liquidation if figures else None
    if estimate is None or estimate.price is None:
        return _NONE_TEXT
    return format_amount(estimate.price.quantize(_CENT))


def _maximum_text(figures: SideFigures | None, base: str, quote: str) -> str:
    """The most a side may order: a quote total on a side sized by quote, a
    base quantity otherwise."""
    if figures is None:
        return _NONE_TEXT
    if figures.sized_by_quote:
        return f"{format_amount(figures.max_total)} {quote}"
    return f"{format_amount(figures.max_quantity)} {base}"


def _show_value(field: QLineEdit, value: Decimal | None) -> None:
    """Rewrites `field` only when it does not already say `value`."""
    if parse_amount(field.text()) == value:
        return
    field.setText("" if value is None else format_amount(value).replace(",", ""))
