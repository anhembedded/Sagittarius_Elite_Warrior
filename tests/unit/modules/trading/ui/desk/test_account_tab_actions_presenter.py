"""`EPIC-028J` — a desk's account tabs run their actions through the desk's
own ports: cancel one, cancel all shown (stopping at a safety-gate
refusal), and close at market only while the position is still the one
confirmed.

@details Split out of `test_account_tabs_presenter.py` at the 400-line
threshold (the third review of PR 307); the desk is `account_tabs_desk.py`'s."""

from __future__ import annotations

from decimal import Decimal

import pytest
from PySide6.QtGui import QAction
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.cancel_order_result import (
    CancelOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_real_money_consent import (
    FakeRealMoneyConsent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.position_close_order import (
    ConfirmedClose,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.position_row import (
    build_position_row,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .account_tabs_desk import AccountTabsDesk
from .account_tabs_fixtures import order, position

# -- actions --------------------------------------------------------------- #


def test_a_confirmed_cancel_removes_the_row_the_venue_cancelled(qtbot) -> None:
    desk = AccountTabsDesk(qtbot)
    desk.activity.holding_open_orders([order("BTCUSDT", "SEW-btc")])
    desk.submission.cancel_answers(CancelOrderResult(None, order("BTCUSDT", "SEW-btc")))
    desk.presenter.show_symbol("BTCUSDT")

    desk.panel.cancelRequested.emit("BTCUSDT", "SEW-btc")

    assert desk.submission.cancelled == [("BTCUSDT", "SEW-btc")]
    assert desk.open_order_ids() == []
    assert desk.message() == "Order cancelled."


def test_cancel_all_cancels_each_order_shown(qtbot) -> None:
    desk = AccountTabsDesk(qtbot)
    desk.activity.holding_open_orders(
        [order("BTCUSDT", "SEW-btc"), order("ETHUSDT", "SEW-eth")]
    )
    desk.submission.cancel_answers(CancelOrderResult(None, order()))
    desk.presenter.show_symbol("BTCUSDT")

    desk.panel.findChild(QAction, "actCancelAllOrders").trigger()

    assert sorted(desk.submission.cancelled) == [
        ("BTCUSDT", "SEW-btc"),
        ("ETHUSDT", "SEW-eth"),
    ]
    assert desk.open_order_ids() == []
    assert desk.message() == "Cancelled 2 of 2 orders."


def test_a_safety_gate_refusal_stops_cancel_all_and_keeps_the_rows(qtbot) -> None:
    desk = AccountTabsDesk(qtbot)
    desk.activity.holding_open_orders(
        [order("BTCUSDT", "SEW-btc"), order("ETHUSDT", "SEW-eth")]
    )
    desk.submission.cancel_answers(
        CancelOrderResult(ExecuteOrderSafetyGate.TRADING_SWITCH_OFF, None)
    )
    desk.presenter.show_symbol("BTCUSDT")

    desk.panel.findChild(QAction, "actCancelAllOrders").trigger()

    assert len(desk.submission.cancelled) == 1
    assert desk.open_order_ids() == ["SEW-btc", "SEW-eth"]
    assert desk.message().startswith("Cancelled 0 of 2 orders.")


def _confirmed(amount: str = "0.02") -> ConfirmedClose:
    """The close the user confirmed, from the row of a position of `amount`."""
    row = build_position_row(position("BTCUSDT", amount))
    return ConfirmedClose(row.symbol, row.side, row.quantity)


def _accepts_one_close(desk: AccountTabsDesk) -> None:
    desk.submission.submit_answers(
        ExecuteOrderResult(
            blocked_by=None, preview=None, limit_checks=(), submitted_order=order()
        )
    )


def test_close_at_market_sizes_the_order_from_the_position_read_now(qtbot) -> None:
    """The row said long 0.02; the venue now reports long 0.015."""
    desk = AccountTabsDesk(qtbot)
    desk.snapshot.holding([position("BTCUSDT", "0.02")])
    _accepts_one_close(desk)
    desk.presenter.show_symbol("BTCUSDT")
    desk.snapshot.holding([position("BTCUSDT", "0.015")])

    desk.panel.closePositionRequested.emit(_confirmed("0.02"))

    (sent,) = desk.submission.submitted_live
    assert (sent.side, sent.quantity, sent.reduce_only) == (
        OrderSide.SELL,
        Decimal("0.015"),
        True,
    )
    assert sent.order_type is OrderType.MARKET
    assert desk.message() == "Close order sent for BTCUSDT."


@pytest.mark.parametrize(
    ("now", "says"),
    [("-0.02", "turned SHORT 0.02"), ("0.03", "grew to LONG 0.03")],
)
def test_a_position_that_is_no_longer_the_one_confirmed_is_not_closed(
    qtbot, now: str, says: str
) -> None:
    """The PR #307 review: the user confirmed closing long 0.02; a position
    that flipped or grew meanwhile is one they never saw."""
    desk = AccountTabsDesk(qtbot)
    desk.snapshot.holding([position("BTCUSDT", "0.02")])
    _accepts_one_close(desk)
    desk.presenter.show_symbol("BTCUSDT")
    desk.snapshot.holding([position("BTCUSDT", now)])

    desk.panel.closePositionRequested.emit(_confirmed("0.02"))

    assert desk.submission.submitted_live == []
    assert says in desk.message()
    assert desk.message().endswith("Nothing was sent.")


def test_closing_a_position_already_gone_sends_nothing(qtbot) -> None:
    desk = AccountTabsDesk(qtbot)
    desk.presenter.show_symbol("BTCUSDT")

    desk.panel.closePositionRequested.emit(_confirmed())

    assert desk.submission.submitted_live == []
    assert desk.message() == "No open BTCUSDT position to close."


def test_a_refused_close_names_the_gate(qtbot) -> None:
    desk = AccountTabsDesk(qtbot)
    desk.snapshot.holding([position("BTCUSDT")])
    desk.submission.submit_answers(
        ExecuteOrderResult(
            blocked_by=ExecuteOrderSafetyGate.TRADING_SWITCH_OFF,
            preview=None,
            limit_checks=(),
            submitted_order=None,
        )
    )
    desk.presenter.show_symbol("BTCUSDT")

    desk.panel.closePositionRequested.emit(_confirmed())

    assert "order session" in desk.message().lower()


def test_closing_on_a_mainnet_venue_asks_about_real_money_and_a_no_sends_nothing(
    qtbot,
) -> None:
    """A close is a market order (`EPIC-034` D3, D11): it can be the first order of
    a session, and its own confirmation does not say the account is real."""
    consent = FakeRealMoneyConsent(agrees=False)
    desk = AccountTabsDesk(qtbot, venue=TradingVenue.FUTURES_MAINNET, consent=consent)
    desk.snapshot.holding([position("BTCUSDT", "0.02")])
    _accepts_one_close(desk)
    desk.presenter.show_symbol("BTCUSDT")

    desk.panel.closePositionRequested.emit(_confirmed())

    assert consent.asked == [(TradingVenue.FUTURES_MAINNET, "close a position")]
    assert desk.submission.submitted_live == []


def test_closing_on_a_mainnet_venue_goes_on_once_real_money_is_agreed(qtbot) -> None:
    consent = FakeRealMoneyConsent(agrees=True)
    desk = AccountTabsDesk(qtbot, venue=TradingVenue.FUTURES_MAINNET, consent=consent)
    desk.snapshot.holding([position("BTCUSDT", "0.02")])
    _accepts_one_close(desk)
    desk.presenter.show_symbol("BTCUSDT")

    desk.panel.closePositionRequested.emit(_confirmed())

    assert len(desk.submission.submitted_live) == 1


def test_closing_on_a_testnet_asks_nothing(qtbot) -> None:
    consent = FakeRealMoneyConsent(agrees=False)
    desk = AccountTabsDesk(qtbot, consent=consent)
    desk.snapshot.holding([position("BTCUSDT", "0.02")])
    _accepts_one_close(desk)
    desk.presenter.show_symbol("BTCUSDT")

    desk.panel.closePositionRequested.emit(_confirmed())

    assert consent.asked == []
    assert len(desk.submission.submitted_live) == 1
