"""`EPIC-028I` — the Futures panel's widgets: reduce-only and the margin and
leverage chips appear on a desk with leverage only; the TP/SL box shows each
side's TP and SL fields; the chips show the exchange's setting and ask
through the view model; the cost and the liquidation estimate are shown.

@details Real widgets and real clicks (`qtbot`)."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    desk_profile_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_panel import (
    OrderEntryPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_view_model import (
    OrderEntryViewModel,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.readout_slot import ReadoutSlot

from .futures_entry_fixtures import MARK, futures_context, futures_reads

_SETTING = FuturesSymbolSetting("BTCUSDT", 10, MarginType.CROSSED, Decimal(10**6))


def _click_box(qtbot, box: QCheckBox) -> None:
    """On the box itself: a check box laid out wider than its text takes a
    click only on its indicator and label."""
    qtbot.mouseClick(box, Qt.MouseButton.LeftButton, pos=QPoint(4, box.height() // 2))


def _panel(qtbot, venue: TradingVenue = TradingVenue.FUTURES_TESTNET):
    vm = OrderEntryViewModel(desk_profile_for(venue))
    vm.begin_symbol("BTCUSDT")
    panel = OrderEntryPanel(vm)
    qtbot.addWidget(panel)
    panel.show()
    return vm, panel


def test_only_a_desk_with_leverage_shows_its_controls(qtbot) -> None:
    _, futures = _panel(qtbot)
    _, spot = _panel(qtbot, TradingVenue.SPOT_TESTNET)

    for name in ("chkReduceOnly", "cboMarginType", "spnLeverage"):
        assert futures.findChild(QWidget, name) is not None
        assert spot.findChild(QWidget, name) is None
    assert spot.findChild(QComboBox, "cboTimeInForce") is not None


def test_the_tp_sl_box_shows_each_sides_fields(qtbot) -> None:
    vm, panel = _panel(qtbot)
    take_profit = panel.findChild(QLineEdit, "txtTakeProfitBuy")
    assert not take_profit.isVisible()

    _click_box(qtbot, panel.findChild(QCheckBox, "chkTpSl"))
    qtbot.keyClicks(take_profit, "63000")

    assert take_profit.isVisible()
    assert vm.options.tp_sl_enabled
    levels = vm.options.protection(EntrySide.BUY)
    assert levels is not None and levels.take_profit == Decimal(63000)


def test_the_chips_show_the_exchanges_setting_and_ask_for_a_change(qtbot) -> None:
    vm, panel = _panel(qtbot)
    leverage = panel.findChild(QSpinBox, "spnLeverage")
    apply = panel.findChild(QPushButton, "btnSetLeverage")
    assert not apply.isEnabled()  # nothing read yet

    vm.options.show_setting(_SETTING)
    asked: list[int] = []
    vm.options.leverageRequested.connect(asked.append)
    leverage.setValue(25)
    qtbot.mouseClick(apply, Qt.MouseButton.LeftButton)

    assert asked == [25]
    assert panel.findChild(QComboBox, "cboMarginType").currentText() == "Cross"


def test_reduce_only_is_one_box_for_both_sides(qtbot) -> None:
    vm, panel = _panel(qtbot)

    _click_box(qtbot, panel.findChild(QCheckBox, "chkReduceOnly"))

    assert vm.options.reduce_only


def test_the_cost_and_the_liquidation_estimate_are_shown(qtbot) -> None:
    vm, panel = _panel(qtbot)
    vm.set_context(
        futures_context(
            available=Decimal(100), reads=futures_reads(wallet=Decimal(100))
        )
    )
    vm.set_last_price(MARK)
    vm.set_price(EntrySide.BUY, "60000")
    vm.set_quantity(EntrySide.BUY, "0.01")

    figures = panel.findChild(ReadoutSlot, "roFiguresBuy")
    cost = figures.value_text("cost")
    liquidation = figures.value_text("liquidation")

    assert cost == "60.00"
    assert liquidation not in (None, "")
    # The estimate says what it leaves out, on its value.
    value = figures.findChild(QLabel, "readout::liquidation")
    assert "other positions" in value.toolTip()
