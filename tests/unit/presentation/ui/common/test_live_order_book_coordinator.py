"""`EPIC-023A` follow-up — `LiveOrderBookCoordinator`, extracted out of
`TradingPresenter` and `DashboardPresenter` after both carried a
byte-for-byte copy of the same six methods."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
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
from Sagittarius_Elite_Warrior.src.presentation.ui.common.live_order_book_coordinator import (
    LiveOrderBookCoordinator,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.OpenOrdersTable.open_order_row import (
    build_open_order_row,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.PositionsTable.positions_row import (
    build_position_row,
)


def _position(symbol="BTCUSDT") -> LivePosition:
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


def _order(symbol="BTCUSDT", status=OrderStatus.NEW) -> Order:
    return Order(
        client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.5"),
        status=status,
        price=Decimal("64000.00"),
    )


def _coordinator():
    view = Mock()
    emit_log = Mock()
    coordinator = LiveOrderBookCoordinator(view=view, emit_log=emit_log)
    return coordinator, view, emit_log


def test_order_filled_with_a_live_status_adds_to_open_orders():
    coordinator, view, _ = _coordinator()
    order = _order(status=OrderStatus.NEW)

    coordinator.on_order_filled(order)

    view.set_open_orders.assert_called_once_with([build_open_order_row(order)])


def test_order_filled_with_a_terminal_status_removes_it():
    coordinator, view, _ = _coordinator()
    coordinator.on_order_filled(_order(status=OrderStatus.NEW))
    view.set_open_orders.reset_mock()

    coordinator.on_order_filled(_order(status=OrderStatus.FILLED))

    view.set_open_orders.assert_called_once_with([])


def test_position_changed_updates_the_positions_table():
    coordinator, view, _ = _coordinator()
    position = _position()

    coordinator.on_position_changed(position)

    view.set_positions.assert_called_once_with([build_position_row(position)])


def test_position_closed_removes_it_from_the_positions_table():
    """`BUG-086` regression."""
    coordinator, view, _ = _coordinator()
    position = _position()
    coordinator.on_position_changed(position)
    view.set_positions.reset_mock()

    coordinator.on_position_closed(position.symbol)

    view.set_positions.assert_called_once_with([])


def test_position_closed_for_an_unknown_symbol_is_a_no_op():
    coordinator, view, _ = _coordinator()

    coordinator.on_position_closed("ETHUSDT")

    view.set_positions.assert_called_once_with([])


def test_order_blocked_reports_through_emit_log():
    """`BUG-084`."""
    coordinator, _, emit_log = _coordinator()

    coordinator.on_order_blocked("BTCUSDT", "max_notional_per_order")

    emit_log.assert_called_once_with(
        "Live order blocked (BTCUSDT): max_notional_per_order"
    )


def test_replace_all_seeds_both_tables_from_a_reconciliation_snapshot():
    coordinator, view, _ = _coordinator()
    position = _position()
    order = _order()

    coordinator.replace_all(positions=[position], open_orders=[order])

    view.set_positions.assert_called_once_with([build_position_row(position)])
    view.set_open_orders.assert_called_once_with([build_open_order_row(order)])


def test_replace_all_with_empty_snapshots_clears_both_tables():
    coordinator, view, _ = _coordinator()
    coordinator.on_position_changed(_position())
    coordinator.on_order_filled(_order())
    view.set_positions.reset_mock()
    view.set_open_orders.reset_mock()

    coordinator.replace_all(positions=[], open_orders=[])

    view.set_positions.assert_called_once_with([])
    view.set_open_orders.assert_called_once_with([])
