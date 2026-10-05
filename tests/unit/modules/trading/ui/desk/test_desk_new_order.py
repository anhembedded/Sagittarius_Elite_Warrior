"""`EPIC-033R` — each desk's Trade → New order… (F9) moves the keyboard focus
to its order entry's first field and places nothing; it is disabled while the
desk cannot trade."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_entry_terms import (
    FakeOrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    FakeVenueTradingPorts,
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_commands import (
    new_order_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.futures_desk_screen import (
    FUTURES_DESK_ROUTE,
    futures_desk_screen,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.spot_desk_screen import (
    SPOT_DESK_ROUTE,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.conftest import fake_container, real_contributions

from .desk_actions import bind_desk_actions
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


def test_the_trading_module_contributes_new_order_on_f9_to_each_desk() -> None:
    commands = {
        command.command_id: command for command in real_contributions(Mock()).commands()
    }

    for venue, route in ((FUTURES, FUTURES_DESK_ROUTE), (SPOT, SPOT_DESK_ROUTE)):
        command = commands[new_order_id(venue)]
        assert command.mode == route
        assert command.shortcut == "F9"
        assert command.text == "&New order…"
        assert command.menu_path == ("T&rade",)


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


def test_new_order_is_disabled_for_the_whole_run_on_a_venue_that_is_off(
    qtbot,
) -> None:
    container = fake_container(
        {IVenueTradingPorts: FakeVenueTradingPorts(fake_venue_ports(SPOT))}
    )
    screen = futures_desk_screen(container)
    view = screen.view_factory()
    qtbot.addWidget(view)
    presenter = screen.presenter_factory(view, container)
    assert view.findChild(QLabel, "lblDeskDisabled") is not None

    actions = bind_desk_actions(view, presenter, FUTURES)

    assert actions.registry.unbound() == ()
    assert not actions.new_order.isEnabled()
