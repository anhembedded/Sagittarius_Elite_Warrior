"""`EPIC-028J` — a desk's account tabs load from the venue when the desk
opens, keep current from the venue's own events, page a history over a
fixed span, and run their actions through the desk's own ports.

@details Every port is a verified fake from `contracts/testing`; the bus is
the engine's real `MemoryEventBus` behind the real `OrderFeed`; the worker
pool runs inline (or held, to supersede a read)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QCheckBox, QLabel
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.cancel_order_result import (
    CancelOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_request import (
    HistoryRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_activity import (
    FakeAccountActivity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_submission import (
    FakeOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.position_close_order import (
    ConfirmedClose,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.account_tab_confirmations import (
    AccountTabConfirmations,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.account_tabs_panel import (
    AccountTabsPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.account_tabs_presenter import (
    AccountTabsPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_tabs_loader import (
    DESK_HISTORY_SPAN,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_view import (
    HistoryKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    HeldTab,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.position_row import (
    build_position_row,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_feed import OrderFeed
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import (
    MemoryEventBus,
)

from .account_tabs_fixtures import NOW, order, order_record, position
from .order_entry_fixtures import HeldThreadManager, InlineThreadManager, spot_status

_FUTURES = TradingVenue.FUTURES_TESTNET


class _Desk:
    """One Futures desk's tabs over fakes, every dialog answered Yes."""

    def __init__(self, qtbot, threads=None) -> None:
        self.now = NOW
        self.bus = MemoryEventBus()
        self.activity = FakeAccountActivity()
        self.snapshot = FakeAccountSnapshot()
        self.submission = FakeOrderSubmission()
        self.threads = threads or InlineThreadManager()
        self.panel = AccountTabsPanel(
            HeldTab.POSITIONS,
            AccountTabConfirmations(
                cancel_one=lambda _r: True,
                cancel_all=lambda _r: True,
                close_position=lambda _r: True,
            ),
        )
        qtbot.addWidget(self.panel)
        self.presenter = AccountTabsPresenter(
            self.panel,
            fake_venue_ports(
                _FUTURES,
                account_activity=self.activity,
                account_snapshot=self.snapshot,
                order_submission=self.submission,
            ),
            OrderFeed(self.bus, _FUTURES, parent=self.panel),
            self.threads,
            clock=lambda: self.now,
        )

    def open_order_ids(self) -> list[str]:
        model = self.panel.open_orders_panel.table.model().sourceModel()
        return sorted(row.client_order_id for row in model.rows)

    def position_symbols(self) -> list[str]:
        model = self.panel.positions_panel.table.model().sourceModel()
        return sorted(row.symbol for row in model.rows)

    def message(self) -> str:
        return self.panel.findChild(QLabel, "lblAccountTabsMessage").text()


def _fill(venue: TradingVenue, client_order_id: str = "SEW-new") -> OrderFilledEvent:
    return OrderFilledEvent(
        order=order("BTCUSDT", client_order_id),
        fill_price=Decimal(0),
        fill_quantity=Decimal(0),
        venue=venue,
    )


# -- loading --------------------------------------------------------------- #


def test_a_desk_opened_after_an_order_was_placed_elsewhere_lists_it(qtbot) -> None:
    desk = _Desk(qtbot)
    desk.activity.holding_open_orders([order("ETHUSDT", "web_placed_in_binance_ui")])
    desk.snapshot.holding([position("BTCUSDT")])

    desk.presenter.show_symbol("BTCUSDT")

    assert desk.open_order_ids() == ["web_placed_in_binance_ui"]
    assert desk.position_symbols() == ["BTCUSDT"]


def test_both_histories_open_on_every_pair_over_the_last_seven_days(qtbot) -> None:
    desk = _Desk(qtbot)
    desk.activity.holding_history([order_record()], scanned_symbols=("BTCUSDT",))

    desk.presenter.show_symbol("BTCUSDT")

    expected = HistoryRequest(symbol=None, since=NOW - DESK_HISTORY_SPAN)
    assert desk.activity.order_requests == [expected]
    assert desk.activity.trade_requests == [expected]
    model = desk.panel.history_panel(HistoryKind.ORDERS).table.model().sourceModel()
    assert [row.symbol for row in model.rows] == ["BTCUSDT"]


def test_paging_keeps_the_span_the_history_opened_with(qtbot) -> None:
    """A later `since` on each click would miss `CachedAccountHistoryReader`
    and re-read the exchange (`EPIC-028Q`)."""
    desk = _Desk(qtbot)
    desk.activity.holding_history([order_record()] * 120)
    desk.presenter.show_symbol("BTCUSDT")
    desk.now = NOW + timedelta(minutes=5)

    desk.panel.historyPageRequested.emit(HistoryKind.ORDERS.value, 2)

    assert desk.activity.order_requests[-1] == HistoryRequest(
        symbol=None, since=NOW - DESK_HISTORY_SPAN, page=2
    )


def test_hide_other_pairs_reopens_the_histories_on_the_desks_symbol(qtbot) -> None:
    desk = _Desk(qtbot)
    desk.presenter.show_symbol("BTCUSDT")
    desk.now = NOW + timedelta(minutes=5)

    desk.panel.findChild(QCheckBox, "chkHideOtherPairs").setChecked(True)

    expected = HistoryRequest(symbol="BTCUSDT", since=desk.now - DESK_HISTORY_SPAN)
    assert desk.activity.order_requests[-1] == expected
    assert desk.activity.trade_requests[-1] == expected


def test_a_failed_history_read_is_said_in_the_tab(qtbot) -> None:
    desk = _Desk(qtbot)
    desk.activity.history_raises(RuntimeError("the venue did not answer"))

    desk.presenter.show_symbol("BTCUSDT")

    empty = desk.panel.findChild(QLabel, "lblTradeHistoryEmpty").text()
    assert "the venue did not answer" in empty


def test_a_superseded_load_is_dropped(qtbot) -> None:
    held = HeldThreadManager()
    desk = _Desk(qtbot, held)
    desk.activity.holding_open_orders([order("BTCUSDT", "SEW-first")])
    desk.presenter.show_symbol("BTCUSDT")
    first_load = len(held.pending) - 3  # the live read, then the two histories
    desk.activity.holding_open_orders([order("BTCUSDT", "SEW-second")])
    desk.presenter.show_symbol("BTCUSDT")
    second_load = len(held.pending) - 3

    held.run(second_load)
    held.run(first_load)

    assert desk.open_order_ids() == ["SEW-second"]


# -- events ---------------------------------------------------------------- #


def test_an_order_of_this_venue_joins_the_table_and_rereads_the_histories(
    qtbot, qapp
) -> None:
    desk = _Desk(qtbot)
    desk.presenter.show_symbol("BTCUSDT")
    reads = len(desk.activity.order_requests)

    desk.bus.emit(_fill(TradingVenue.SPOT_TESTNET, "SEW-spot"))
    desk.bus.emit(_fill(_FUTURES, "SEW-futures"))
    qapp.processEvents()

    assert desk.open_order_ids() == ["SEW-futures"]
    assert len(desk.activity.order_requests) == reads + 1
    assert desk.activity.order_requests[-1].since == NOW - DESK_HISTORY_SPAN


# -- actions --------------------------------------------------------------- #


def test_a_confirmed_cancel_removes_the_row_the_venue_cancelled(qtbot) -> None:
    desk = _Desk(qtbot)
    desk.activity.holding_open_orders([order("BTCUSDT", "SEW-btc")])
    desk.submission.cancel_answers(CancelOrderResult(None, order("BTCUSDT", "SEW-btc")))
    desk.presenter.show_symbol("BTCUSDT")

    desk.panel.cancelRequested.emit("BTCUSDT", "SEW-btc")

    assert desk.submission.cancelled == [("BTCUSDT", "SEW-btc")]
    assert desk.open_order_ids() == []
    assert desk.message() == "Order cancelled."


def test_cancel_all_cancels_each_order_shown(qtbot) -> None:
    desk = _Desk(qtbot)
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
    desk = _Desk(qtbot)
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


def _accepts_one_close(desk: _Desk) -> None:
    desk.submission.submit_answers(
        ExecuteOrderResult(
            blocked_by=None, preview=None, limit_checks=(), submitted_order=order()
        )
    )


def test_close_at_market_sizes_the_order_from_the_position_read_now(qtbot) -> None:
    """The row said long 0.02; the venue now reports long 0.015."""
    desk = _Desk(qtbot)
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
    desk = _Desk(qtbot)
    desk.snapshot.holding([position("BTCUSDT", "0.02")])
    _accepts_one_close(desk)
    desk.presenter.show_symbol("BTCUSDT")
    desk.snapshot.holding([position("BTCUSDT", now)])

    desk.panel.closePositionRequested.emit(_confirmed("0.02"))

    assert desk.submission.submitted_live == []
    assert says in desk.message()
    assert desk.message().endswith("Nothing was sent.")


def test_closing_a_position_already_gone_sends_nothing(qtbot) -> None:
    desk = _Desk(qtbot)
    desk.presenter.show_symbol("BTCUSDT")

    desk.panel.closePositionRequested.emit(_confirmed())

    assert desk.submission.submitted_live == []
    assert desk.message() == "No open BTCUSDT position to close."


def test_a_refused_close_names_the_gate(qtbot) -> None:
    desk = _Desk(qtbot)
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

    assert "trading" in desk.message().lower()


def test_a_spot_desk_lists_its_assets_from_the_account(qtbot) -> None:
    activity = FakeAccountActivity()
    panel = AccountTabsPanel(HeldTab.ASSETS)
    qtbot.addWidget(panel)
    presenter = AccountTabsPresenter(
        panel,
        fake_venue_ports(
            TradingVenue.SPOT_TESTNET,
            account_activity=activity,
            account_snapshot=FakeAccountSnapshot(spot_status(btc_free=Decimal("0.5"))),
        ),
        OrderFeed(MemoryEventBus(), TradingVenue.SPOT_TESTNET, parent=panel),
        InlineThreadManager(),
        clock=lambda: NOW,
    )

    presenter.show_symbol("BTCUSDT")
    presenter.update_last_price(Decimal(60000))

    rows = panel.holdings_panel.table.model().sourceModel().rows
    assert sorted(row.asset for row in rows) == ["BTC", "USDT"]
    btc = next(row for row in rows if row.asset == "BTC")
    assert btc.value_text != "—"
