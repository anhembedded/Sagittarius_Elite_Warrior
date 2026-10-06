"""`EPIC-028J` — a desk's account tabs load from the venue when the desk
opens, keep current from the venue's own events, and page a history over a
fixed span. Their actions are `test_account_tab_actions_presenter.py`'s.

@details Every port is a verified fake from `contracts/testing`; the bus is
the engine's real `MemoryEventBus` behind the real `OrderFeed`; the worker
pool runs inline (or held, to supersede a read)."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from PySide6.QtWidgets import QLabel
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_ended_event import (
    OrderEndedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_request import (
    HistoryRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_activity import (
    FakeAccountActivity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    fake_venue_ports,
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
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_feed import OrderFeed
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import (
    MemoryEventBus,
)

from .account_tabs_desk import FUTURES, AccountTabsDesk
from .account_tabs_fixtures import NOW, order, order_record, position
from .order_entry_fixtures import HeldThreadManager, InlineThreadManager, spot_status


def _fill(venue: TradingVenue, client_order_id: str = "SEW-new") -> OrderFilledEvent:
    return OrderFilledEvent(
        order=order("BTCUSDT", client_order_id),
        fill_price=Decimal(0),
        fill_quantity=Decimal(0),
        venue=venue,
    )


# -- loading --------------------------------------------------------------- #


def test_a_desk_opened_after_an_order_was_placed_elsewhere_lists_it(qtbot) -> None:
    desk = AccountTabsDesk(qtbot)
    desk.activity.holding_open_orders([order("ETHUSDT", "web_placed_in_binance_ui")])
    desk.snapshot.holding([position("BTCUSDT")])

    desk.presenter.show_symbol("BTCUSDT")

    assert desk.open_order_ids() == ["web_placed_in_binance_ui"]
    assert desk.position_symbols() == ["BTCUSDT"]


def test_both_histories_open_on_every_pair_over_the_last_seven_days(qtbot) -> None:
    desk = AccountTabsDesk(qtbot)
    desk.activity.holding_history([order_record()], scanned_symbols=("BTCUSDT",))

    desk.presenter.show_symbol("BTCUSDT")

    expected = HistoryRequest(
        symbol=None, since=NOW - DESK_HISTORY_SPAN, desk_symbol="BTCUSDT"
    )
    assert desk.activity.order_requests == [expected]
    assert desk.activity.trade_requests == [expected]
    model = desk.panel.history_panel(HistoryKind.ORDERS).table.model().sourceModel()
    assert [row.symbol for row in model.rows] == ["BTCUSDT"]


def test_paging_keeps_the_span_the_history_opened_with(qtbot) -> None:
    """A later `since` on each click would miss `CachedAccountHistoryReader`
    and re-read the exchange (`EPIC-028Q`)."""
    desk = AccountTabsDesk(qtbot)
    desk.activity.holding_history([order_record()] * 120)
    desk.presenter.show_symbol("BTCUSDT")
    desk.now = NOW + timedelta(minutes=5)

    desk.panel.historyPageRequested.emit(HistoryKind.ORDERS.value, 2)

    assert desk.activity.order_requests[-1] == HistoryRequest(
        symbol=None, since=NOW - DESK_HISTORY_SPAN, page=2, desk_symbol="BTCUSDT"
    )


def test_hide_other_pairs_reopens_the_histories_on_the_desks_symbol(qtbot) -> None:
    desk = AccountTabsDesk(qtbot)
    desk.presenter.show_symbol("BTCUSDT")
    desk.now = NOW + timedelta(minutes=5)

    desk.panel.set_hide_other_pairs(True)

    expected = HistoryRequest(
        symbol="BTCUSDT", since=desk.now - DESK_HISTORY_SPAN, desk_symbol="BTCUSDT"
    )
    assert desk.activity.order_requests[-1] == expected
    assert desk.activity.trade_requests[-1] == expected


def test_a_failed_history_read_is_said_in_the_tab(qtbot) -> None:
    desk = AccountTabsDesk(qtbot)
    desk.activity.history_raises(RuntimeError("the venue did not answer"))

    desk.presenter.show_symbol("BTCUSDT")

    empty = desk.panel.findChild(QLabel, "lblTradeHistoryEmpty").text()
    assert "the venue did not answer" in empty


def test_a_superseded_load_is_dropped(qtbot) -> None:
    held = HeldThreadManager()
    desk = AccountTabsDesk(qtbot, held)
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
    desk = AccountTabsDesk(qtbot)
    desk.presenter.show_symbol("BTCUSDT")
    reads = len(desk.activity.order_requests)

    desk.bus.emit(_fill(TradingVenue.SPOT_TESTNET, "SEW-spot"))
    desk.bus.emit(_fill(FUTURES, "SEW-futures"))
    qapp.processEvents()

    assert desk.open_order_ids() == ["SEW-futures"]
    assert len(desk.activity.order_requests) == reads + 1
    assert desk.activity.order_requests[-1].since == NOW - DESK_HISTORY_SPAN


def test_an_order_ended_elsewhere_leaves_open_orders(qtbot, qapp) -> None:
    """The review of PR 307: an order cancelled from the other desk, from
    Binance's site or by the exchange stayed listed until the desk reloaded.
    Another venue's ending touches nothing."""
    desk = AccountTabsDesk(qtbot)
    desk.activity.holding_open_orders(
        [order("BTCUSDT", "SEW-btc"), order("ETHUSDT", "SEW-eth")]
    )
    desk.presenter.show_symbol("BTCUSDT")
    reads = len(desk.activity.order_requests)

    ended = replace(order("BTCUSDT", "SEW-btc"), status=OrderStatus.CANCELED)
    desk.bus.emit(OrderEndedEvent(order=ended, venue=TradingVenue.SPOT_TESTNET))
    qapp.processEvents()
    assert desk.open_order_ids() == ["SEW-btc", "SEW-eth"]

    desk.bus.emit(OrderEndedEvent(order=ended, venue=FUTURES))
    qapp.processEvents()

    assert desk.open_order_ids() == ["SEW-eth"]
    assert len(desk.activity.order_requests) == reads + 1


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
    assert btc.value is not None
