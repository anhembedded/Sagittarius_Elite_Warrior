"""`EPIC-033R` — Trade → New order… (F9) moves the keyboard focus to the
chosen venue's order entry's first field and places nothing; it is disabled
while that desk cannot trade (`EPIC-033I`: one command for the mode). What
the module contributes is `trade/test_trade_commands.py`'s."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QLineEdit
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_entry_terms import (
    FakeOrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .desk_screen_fixtures import Desk, build_desk
from .futures_entry_fixtures import futures_status, futures_terms
from .order_entry_fixtures import TERMS, spot_status

FUTURES = TradingVenue.FUTURES_TESTNET
SPOT = TradingVenue.SPOT_TESTNET
VENUES = [FUTURES, SPOT]


def _desk(qtbot, venue: TradingVenue) -> Desk:
    """`venue`'s desk with `BTCUSDT`'s terms read, so its order entry takes
    input."""
    if venue is FUTURES:
        return build_desk(
            qtbot,
            venue,
            account_snapshot=FakeAccountSnapshot(futures_status()),
            order_entry_terms=futures_terms(),
        )
    return build_desk(
        qtbot,
        venue,
        account_snapshot=FakeAccountSnapshot(spot_status()),
        order_entry_terms=FakeOrderEntryTerms(TERMS),
    )


def _shown(qtbot, desk: Desk) -> Desk:
    """The desk in an active window, so a field can take the focus."""
    desk.view.show()
    qtbot.waitExposed(desk.view)
    desk.view.activateWindow()
    return desk


def _field(desk: Desk, name: str) -> QLineEdit:
    field = desk.view.findChild(QLineEdit, name)
    assert field is not None
    return field


@pytest.mark.parametrize("venue", VENUES)
def test_new_order_focuses_the_first_field_and_places_nothing(qtbot, venue) -> None:
    desk = _shown(qtbot, _desk(qtbot, venue))
    new_order = desk.actions.new_order
    assert new_order.shortcut() == QKeySequence("F9")
    assert new_order.isEnabled()

    new_order.trigger()

    price = _field(desk, "txtPriceBuy")
    qtbot.waitUntil(lambda: QApplication.focusWidget() is price)
    assert desk.submission.previewed == []
    assert desk.submission.submitted_live == []
    assert desk.submission.submitted_dry == []


@pytest.mark.parametrize("venue", VENUES)
def test_the_first_field_follows_the_order_type(qtbot, venue) -> None:
    """A market order has no price: its first field is the amount; a
    stop-limit's is the stop, drawn above the price."""
    desk = _shown(qtbot, _desk(qtbot, venue))
    orders = desk.presenter.orders

    orders.set_order_type(OrderType.MARKET)
    desk.actions.new_order.trigger()
    amount = _field(desk, "txtAmountBuy")
    total = _field(desk, "txtTotalBuy")
    first = amount if amount.isVisible() else total
    qtbot.waitUntil(lambda: QApplication.focusWidget() is first)

    orders.set_order_type(OrderType.STOP_LIMIT)
    desk.actions.new_order.trigger()
    stop = _field(desk, "txtStopPriceBuy")
    qtbot.waitUntil(lambda: QApplication.focusWidget() is stop)


@pytest.mark.parametrize("venue", VENUES)
def test_new_order_selects_what_the_first_field_holds(qtbot, venue) -> None:
    """Typing after F9 replaces the price instead of appending to it."""
    desk = _shown(qtbot, _desk(qtbot, venue))
    desk.presenter.orders.set_price(EntrySide.BUY, "60000")
    price = _field(desk, "txtPriceBuy")
    assert price.text() == "60000"

    desk.actions.new_order.trigger()

    qtbot.waitUntil(lambda: QApplication.focusWidget() is price)
    assert price.selectedText() == "60000"


@pytest.mark.parametrize("venue", VENUES)
def test_new_order_is_disabled_while_the_order_entry_cannot_take_an_order(
    qtbot, venue
) -> None:
    desk = _desk(qtbot, venue)
    orders = desk.presenter.orders
    new_order = desk.actions.new_order

    orders.set_busy(True, "Placing the order...")
    assert not new_order.isEnabled()
    orders.show_result("Placed.", is_error=False)
    assert new_order.isEnabled()

    orders.begin_symbol("ETHUSDT")
    assert not new_order.isEnabled()
