"""`EPIC-028H` — the panel's widgets write every edit to the view model and
show what it computes; the submit button is only live when the side may
submit. `EPIC-028O`: the stop field, the total field of a market buy, the
BBO button and the notional cap."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import (
    QCheckBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QTabBar,
    QToolButton,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
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

from .order_entry_fixtures import SYMBOL, spot_context


def _panel(qtbot, *, loaded: bool = True, free_base: Decimal = Decimal("0.5")):
    vm = OrderEntryViewModel(desk_profile_for(TradingVenue.SPOT_TESTNET))
    vm.begin_symbol(SYMBOL)
    if loaded:
        vm.set_context(spot_context(free_base=free_base))
    panel = OrderEntryPanel(vm)
    qtbot.addWidget(panel)
    return vm, panel


def _child[T](panel: OrderEntryPanel, kind: type[T], name: str) -> T:
    widget = panel.findChild(kind, name)
    assert widget is not None, name
    return widget


def test_one_tab_per_offered_order_type_and_switching_changes_the_type(
    qtbot,
) -> None:
    vm, panel = _panel(qtbot)
    tabs = _child(panel, QTabBar, "tabOrderType")

    assert [tabs.tabText(i) for i in range(tabs.count())] == [
        "Limit",
        "Market",
        "Stop-limit",
    ]
    tabs.setCurrentIndex(1)

    assert vm.order_type is OrderType.MARKET
    assert not _child(panel, QLineEdit, "txtPriceBuy").isVisibleTo(panel)


def test_typing_updates_the_side_and_its_figures(qtbot) -> None:
    vm, panel = _panel(qtbot)

    qtbot.keyClicks(_child(panel, QLineEdit, "txtPriceBuy"), "100")
    qtbot.keyClicks(_child(panel, QLineEdit, "txtAmountBuy"), "2")

    assert vm.entry(EntrySide.BUY).price == 100
    assert vm.entry(EntrySide.BUY).quantity == 2
    figures = _child(panel, ReadoutSlot, "roFiguresBuy")
    assert figures.value_text("total") == "200.00"
    assert figures.value_text("fee") == "0.2"
    assert figures.value_text("available") == "1,000.00"
    assert _child(panel, QPushButton, "btnSubmitBuy").isEnabled()


def test_the_slider_fills_the_amount(qtbot) -> None:
    vm, panel = _panel(qtbot)
    qtbot.keyClicks(_child(panel, QLineEdit, "txtPriceSell"), "100")

    _child(panel, QSlider, "sldPercentSell").setValue(50)

    assert vm.entry(EntrySide.SELL).quantity == Decimal("0.25")
    assert _child(panel, QLineEdit, "txtAmountSell").text() == "0.25"


def test_sell_is_disabled_without_a_holding(qtbot) -> None:
    _vm, panel = _panel(qtbot, free_base=Decimal(0))

    assert not _child(panel, QPushButton, "btnSubmitSell").isEnabled()
    assert _child(panel, QLabel, "lblProblemSell").text() == "No BTC to sell."


def test_nothing_is_submittable_until_the_terms_are_read(qtbot) -> None:
    _vm, panel = _panel(qtbot, loaded=False)

    assert not _child(panel, QPushButton, "btnSubmitBuy").isEnabled()
    assert not _child(panel, QLineEdit, "txtAmountBuy").isEnabled()
    assert _child(panel, QLabel, "lblOrderEntryStatus").text() == "Loading BTCUSDT..."


def test_the_button_asks_to_submit_its_own_side(qtbot) -> None:
    vm, panel = _panel(qtbot)
    qtbot.keyClicks(_child(panel, QLineEdit, "txtPriceBuy"), "100")
    qtbot.keyClicks(_child(panel, QLineEdit, "txtAmountBuy"), "1")
    requested: list[str] = []
    vm.submitRequested.connect(requested.append)

    _child(panel, QPushButton, "btnSubmitBuy").click()

    assert requested == ["BUY"]


def test_a_busy_panel_locks_its_inputs_and_says_why(qtbot) -> None:
    vm, panel = _panel(qtbot)
    qtbot.keyClicks(_child(panel, QLineEdit, "txtPriceBuy"), "100")
    qtbot.keyClicks(_child(panel, QLineEdit, "txtAmountBuy"), "1")

    vm.set_busy(True, "Sending order...")

    assert not _child(panel, QPushButton, "btnSubmitBuy").isEnabled()
    assert not _child(panel, QTabBar, "tabOrderType").isEnabled()
    assert _child(panel, QLabel, "lblOrderEntryStatus").text() == "Sending order..."


def test_the_spot_tp_sl_toggle_is_shown_disabled_with_its_reason(qtbot) -> None:
    _vm, panel = _panel(qtbot)
    toggle = _child(panel, QCheckBox, "chkTpSl")

    assert toggle.isVisibleTo(panel)
    assert not toggle.isEnabled()
    assert "OCO" in toggle.toolTip()


# -- EPIC-028O -------------------------------------------------------------- #


def test_the_stop_price_field_shows_only_on_the_stop_limit_tab(qtbot) -> None:
    vm, panel = _panel(qtbot)
    stop = _child(panel, QLineEdit, "txtStopPriceBuy")
    assert not stop.isVisibleTo(panel)

    _child(panel, QTabBar, "tabOrderType").setCurrentIndex(2)
    qtbot.keyClicks(stop, "105")

    assert vm.order_type is OrderType.STOP_LIMIT
    assert stop.isVisibleTo(panel)
    assert vm.entry(EntrySide.BUY).stop_price == 105


def test_a_market_buy_takes_a_total_and_a_market_sell_an_amount(qtbot) -> None:
    vm, panel = _panel(qtbot)
    vm.set_last_price(Decimal(250))
    _child(panel, QTabBar, "tabOrderType").setCurrentIndex(1)

    total = _child(panel, QLineEdit, "txtTotalBuy")
    qtbot.keyClicks(total, "500")

    assert total.isVisibleTo(panel)
    assert not _child(panel, QLineEdit, "txtAmountBuy").isVisibleTo(panel)
    assert _child(panel, QLineEdit, "txtAmountSell").isVisibleTo(panel)
    assert not _child(panel, QLineEdit, "txtTotalSell").isVisibleTo(panel)
    assert vm.entry(EntrySide.BUY).total == 500
    assert _child(panel, ReadoutSlot, "roFiguresBuy").value_text("maximum") == (
        "1,000.00"
    )
    assert _child(panel, QSlider, "sldPercentBuy").value() == 50
    assert _child(panel, QPushButton, "btnSubmitBuy").isEnabled()


def test_the_best_price_button_asks_for_its_side_and_hides_on_market(qtbot) -> None:
    vm, panel = _panel(qtbot)
    requested: list[str] = []
    vm.bestPriceRequested.connect(requested.append)
    button = _child(panel, QToolButton, "btnBestPriceBuy")

    button.click()
    _child(panel, QTabBar, "tabOrderType").setCurrentIndex(1)

    assert requested == ["BUY"]
    assert "best bid" in button.toolTip()
    assert "best ask" in _child(panel, QToolButton, "btnBestPriceSell").toolTip()
    assert not button.isVisibleTo(panel)


def test_the_maximum_respects_the_app_notional_limit(qtbot) -> None:
    vm = OrderEntryViewModel(desk_profile_for(TradingVenue.SPOT_TESTNET))
    vm.begin_symbol(SYMBOL)
    vm.set_context(spot_context(notional_limit=Decimal(500)))
    panel = OrderEntryPanel(vm)
    qtbot.addWidget(panel)

    qtbot.keyClicks(_child(panel, QLineEdit, "txtPriceBuy"), "100")
    qtbot.keyClicks(_child(panel, QLineEdit, "txtAmountBuy"), "6")

    assert _child(panel, ReadoutSlot, "roFiguresBuy").value_text("maximum") == "5"
    assert "app's limit of 500 USDT" in _child(panel, QLabel, "lblProblemBuy").text()
    assert not _child(panel, QPushButton, "btnSubmitBuy").isEnabled()


def test_the_best_price_button_is_not_offered_on_a_stop_limit(qtbot) -> None:
    # A stop-limit's limit price is where it rests once triggered; the
    # queue's front now is the wrong price for it (PR #305 review).
    _vm, panel = _panel(qtbot)

    _child(panel, QTabBar, "tabOrderType").setCurrentIndex(2)

    assert not _child(panel, QToolButton, "btnBestPriceBuy").isVisibleTo(panel)
    assert _child(panel, QToolButton, "btnLastPriceBuy").isVisibleTo(panel)
