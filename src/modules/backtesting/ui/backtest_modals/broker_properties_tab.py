"""The Strategy Parameters dialog's Properties tab: how the simulated broker
fills the run's orders (BOT-104, BUG-064).

One group box per concern, each a form of labelled stock controls
(`EPIC-033L`); it replaces section headers drawn as an accent label beside a
rule and fields given a fixed height and a style sheet each. The widgets'
values are bound to the view model by the dialog (`BROKER_PROPERTY_FIELDS`);
this tab only builds them and says which widget backs which property.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit.widget_value import (
    mark_uses_item_data,
)

_CURRENCIES = ("USD", "USDT", "BTC", "VND")
_ORDER_SIZE_TYPES = (
    ("% of equity", "percent_of_equity"),
    ("Fixed USD (cash)", "fixed_cash"),
    ("Contracts / coin", "fixed_contracts"),
)
_COMMISSION_TYPES = (
    ("% of order value", "percent"),
    ("USD per order", "cash_per_order"),
    ("USD per contract", "cash_per_contract"),
)
_MAX_PYRAMIDING = 10
_MAX_SLIPPAGE_TICKS = 100
_MAX_LEVERAGE = 125


def _line(object_name: str) -> QLineEdit:
    edit = QLineEdit()
    edit.setObjectName(object_name)
    return edit


def _spin(object_name: str, low: int, high: int) -> QSpinBox:
    spin = QSpinBox()
    spin.setObjectName(object_name)
    spin.setRange(low, high)
    return spin


def _choices(object_name: str, items: tuple[tuple[str, str], ...]) -> QComboBox:
    # The value is each item's data, not the label Qt's USER property would
    # otherwise report.
    combo = mark_uses_item_data(QComboBox())
    combo.setObjectName(object_name)
    for label, value in items:
        combo.addItem(label, value)
    return combo


class BrokerPropertiesTab(QWidget):  # base-exempt: a tab's content
    """@brief Capital, order size, commission, leverage and take profit."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("strategyPropertiesContent")
        self.initial_capital = _line("propInitialCapital")
        self.currency = QComboBox()
        self.currency.setObjectName("propCurrency")
        self.currency.addItems(_CURRENCIES)
        self.order_size_type = _choices("propOrderSizeType", _ORDER_SIZE_TYPES)
        self.order_size_value = _line("propOrderSizeValue")
        self.pyramiding = _spin("propPyramiding", 1, _MAX_PYRAMIDING)
        self.commission_type = _choices("propCommissionType", _COMMISSION_TYPES)
        self.commission_value = _line("propCommissionValue")
        self.slippage_ticks = _spin("propSlippageTicks", 0, _MAX_SLIPPAGE_TICKS)
        self.long_leverage = _spin("propLongLeverage", 1, _MAX_LEVERAGE)
        self.short_leverage = _spin("propShortLeverage", 1, _MAX_LEVERAGE)
        self.take_profit_enabled = QCheckBox("Ta&ke profit at a set percentage")
        self.take_profit_enabled.setObjectName("propTakeProfitEnabled")
        self.take_profit_pct = _line("propTakeProfitPct")
        self.take_profit_pct.setToolTip(
            "Matches the strategy's take_profit_percent parameter."
        )
        # The % field is only editable while the box is on.
        self.take_profit_enabled.toggled.connect(self.take_profit_pct.setEnabled)

        capital = self._group(
            "Capital",
            ("Initial &capital:", self.initial_capital),
            ("C&urrency:", self.currency),
        )
        order_size = self._group(
            "Order size",
            ("Si&ze type:", self.order_size_type),
            ("Size &value:", self.order_size_value),
            ("&Pyramiding (max orders):", self.pyramiding),
        )
        costs = self._group(
            "Commission and slippage",
            ("Co&mmission type:", self.commission_type),
            ("Commission r&ate:", self.commission_value),
            ("&Slippage (ticks):", self.slippage_ticks),
        )
        # EPIC-027D — its own box, so Spot can hide it (not merely disable).
        self.leverage_section = self._group(
            "Leverage",
            ("&Long leverage (x):", self.long_leverage),
            ("S&hort leverage (x):", self.short_leverage),
        )
        self.leverage_section.setObjectName("leverageSection")
        take_profit = QGroupBox("Automatic take profit")
        take_profit_form = QFormLayout(take_profit)
        take_profit_form.addRow(self.take_profit_enabled)
        take_profit_form.addRow("Take profit perc&entage:", self.take_profit_pct)

        layout = QVBoxLayout(self)
        for group in (capital, order_size, costs, self.leverage_section, take_profit):
            layout.addWidget(group)
        layout.addStretch(1)

    @property
    def widgets(self) -> dict[str, QWidget]:
        """Which widget backs each `BrokerPropertyField.key` — and only that
        (BUG-064): adding a broker property is one row here plus one in
        `BROKER_PROPERTY_FIELDS`."""
        return {
            "initial_capital": self.initial_capital,
            "currency": self.currency,
            "order_size_type": self.order_size_type,
            "order_size_text": self.order_size_value,
            "pyramiding": self.pyramiding,
            "commission_type": self.commission_type,
            "commission_text": self.commission_value,
            "slippage_ticks": self.slippage_ticks,
            "long_leverage": self.long_leverage,
            "short_leverage": self.short_leverage,
            "take_profit_enabled": self.take_profit_enabled,
            "take_profit_pct_text": self.take_profit_pct,
        }

    @staticmethod
    def _group(title: str, *rows: tuple[str, QWidget]) -> QGroupBox:
        group = QGroupBox(title)
        form = QFormLayout(group)
        for label, field in rows:
            form.addRow(label, field)
        return group
