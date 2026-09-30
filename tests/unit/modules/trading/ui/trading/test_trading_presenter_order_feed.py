"""`EPIC-021I` — what the Trading screen's `OrderFeed` does to its two live
tables (Positions/Open Orders) and to the chart's fill markers.

Split off `test_trading_presenter_toggle.py` (the PR #295 review: that file
had crossed the 400-line ceiling `architecture-rule.md` §5 applies to tests),
which keeps the Enable/Disable toggle. Same fixtures, from this package's
`conftest.py`; the slots are called directly, as the Feed would deliver them
on the main thread.
"""

from __future__ import annotations

import os
from decimal import Decimal

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.live_order_blocked_event import (
    LiveOrderBlockedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.position_changed_event import (
    PositionChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.position_closed_event import (
    PositionClosedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.open_order_row import (
    build_open_order_row,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.position_row import (
    build_position_row,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def _position(symbol="BTCUSDT") -> LivePosition:
    from datetime import UTC, datetime

    return LivePosition(
        symbol=symbol,
        position_amt=Decimal("0.5"),
        entry_price=Decimal("64000.00"),
        mark_price=Decimal("64500.00"),
        unrealized_pnl=Decimal("10.0"),
        leverage=10,
        margin_type=MarginType.CROSSED,
        liquidation_price=None,
        updated_at=datetime.now(UTC),
    )


def _order(symbol="BTCUSDT", status=OrderStatus.NEW, order_time=None) -> Order:
    return Order(
        client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.5"),
        status=status,
        price=Decimal("64000.00"),
        order_time=order_time,
    )


# ---------------------------------------------------------------------------
# OrderFeed -> the two live tables
# ---------------------------------------------------------------------------


def test_order_filled_with_a_live_status_adds_to_open_orders(presenter, view):
    order = _order(status=OrderStatus.NEW)

    presenter._on_order_filled(
        OrderFilledEvent(
            order=order,
            fill_price=Decimal(0),
            fill_quantity=Decimal(0),
            venue=TradingVenue.FUTURES_TESTNET,
        )
    )

    view.set_open_orders.assert_called_once_with([build_open_order_row(order)])


def test_order_filled_with_a_terminal_status_removes_it(presenter, view):
    live_order = _order(status=OrderStatus.NEW)
    presenter._on_order_filled(
        OrderFilledEvent(
            order=live_order,
            fill_price=Decimal(0),
            fill_quantity=Decimal(0),
            venue=TradingVenue.FUTURES_TESTNET,
        )
    )
    view.set_open_orders.reset_mock()

    filled_order = _order(status=OrderStatus.FILLED)
    presenter._on_order_filled(
        OrderFilledEvent(
            order=filled_order,
            fill_price=Decimal(64000),
            fill_quantity=Decimal("0.5"),
            venue=TradingVenue.FUTURES_TESTNET,
        )
    )

    view.set_open_orders.assert_called_once_with([])


def test_position_changed_updates_the_positions_table(presenter, view):
    position = _position()

    presenter._on_position_changed(
        PositionChangedEvent(position=position, venue=TradingVenue.FUTURES_TESTNET)
    )

    view.set_positions.assert_called_once_with([build_position_row(position)])


def test_position_closed_removes_it_from_the_positions_table(presenter, view):
    """`BUG-086` regression."""
    position = _position()
    presenter._on_position_changed(
        PositionChangedEvent(position=position, venue=TradingVenue.FUTURES_TESTNET)
    )
    view.set_positions.reset_mock()

    presenter._on_position_closed(
        PositionClosedEvent(symbol=position.symbol, venue=TradingVenue.FUTURES_TESTNET)
    )

    view.set_positions.assert_called_once_with([])


def test_position_closed_for_an_unknown_symbol_is_a_no_op(presenter, view):
    presenter._on_position_closed(
        PositionClosedEvent(symbol="ETHUSDT", venue=TradingVenue.FUTURES_TESTNET)
    )

    view.set_positions.assert_called_once_with([])


def test_order_blocked_appears_in_the_screens_own_log_panel(presenter):
    """`BUG-084` — before this fix, a signal-driven order blocked by sizing
    or a trading limit was a log-file-only fact; nothing distinguished
    "no signal fired" from "a signal fired but got blocked" on the Trading
    screen itself."""
    presenter._on_order_blocked(
        LiveOrderBlockedEvent(
            symbol="BTCUSDT",
            reason="max_notional_per_order",
            venue=TradingVenue.FUTURES_TESTNET,
        )
    )

    log_model = presenter._view_model.log_model
    assert log_model.rowCount() == 1
    entry = log_model._entries[0]
    assert entry.level == "info"
    assert "BTCUSDT" in entry.message
    assert "max_notional_per_order" in entry.message


# ---------------------------------------------------------------------------
# OrderFeed -> live-fill chart markers (`EPIC-021K` §2.3/§4 — "Integration:
# OrderFilledEvent -> marker đúng vị trí thời gian/giá trên chart")
# ---------------------------------------------------------------------------


def test_order_filled_renders_a_fill_marker_on_the_active_symbols_chart(
    presenter, view
):
    from datetime import UTC, datetime

    from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_fill_marker import (
        order_filled_marker,
    )

    event = OrderFilledEvent(
        order=_order(
            symbol="BTCUSDT", order_time=datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
        ),
        fill_price=Decimal("64000.00"),
        fill_quantity=Decimal("0.5"),
        venue=TradingVenue.FUTURES_TESTNET,
    )
    assert presenter._active_symbol == "BTCUSDT"

    presenter._on_order_filled(event)

    view.chart.set_script_markers.assert_called_once_with(
        "live_fills", [order_filled_marker(event)]
    )


def test_order_filled_for_a_different_symbol_does_not_touch_the_chart(presenter, view):
    event = OrderFilledEvent(
        order=_order(symbol="ETHUSDT"),
        fill_price=Decimal("3000.00"),
        fill_quantity=Decimal(1),
        venue=TradingVenue.FUTURES_TESTNET,
    )
    assert presenter._active_symbol != "ETHUSDT"

    presenter._on_order_filled(event)

    view.chart.set_script_markers.assert_not_called()
    assert presenter._fill_markers_by_symbol["ETHUSDT"] != []
