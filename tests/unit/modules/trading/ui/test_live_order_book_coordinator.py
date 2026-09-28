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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.live_order_book_coordinator import (
    LiveOrderBookCoordinator,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.holding_row import (
    build_holding_row,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.open_order_row import (
    build_open_order_row,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.position_row import (
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


def _holding(asset="BTC", free=Decimal("0.5"), locked=Decimal(0)) -> SpotHolding:
    return SpotHolding(
        asset=asset, free=free, locked=locked, dust_threshold=Decimal("0.0001")
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


def test_replace_holdings_renders_the_whole_set_with_given_prices():
    """`EPIC-027O` — no incremental `on_holding_*` pair; every
    `HoldingsChangedEvent` already carries the complete account snapshot
    (that event's own docstring)."""
    coordinator, view, _ = _coordinator()
    holding = _holding()
    prices = {"BTC": Decimal(64000)}

    coordinator.replace_holdings([holding], prices)

    view.set_holdings.assert_called_once_with([build_holding_row(holding, prices)])


def test_replace_holdings_with_an_empty_set_clears_the_table():
    coordinator, view, _ = _coordinator()
    coordinator.replace_holdings([_holding()], {})
    view.set_holdings.reset_mock()

    coordinator.replace_holdings([], {})

    view.set_holdings.assert_called_once_with([])


def test_has_holding_is_false_before_any_holdings_are_known():
    coordinator, _, _ = _coordinator()

    assert coordinator.has_holding("BTCUSDT") is False


def test_has_holding_is_true_for_a_non_dust_balance():
    coordinator, _, _ = _coordinator()
    coordinator.replace_holdings([_holding(free=Decimal("0.5"))], {})

    assert coordinator.has_holding("BTCUSDT") is True


def test_has_holding_is_false_for_a_dust_balance():
    """The manual order card's SELL button must not enable on a leftover
    balance too small to actually sell."""
    coordinator, _, _ = _coordinator()
    coordinator.replace_holdings(
        [_holding(free=Decimal("0.00001"), locked=Decimal(0))], {}
    )

    assert coordinator.has_holding("BTCUSDT") is False


def test_has_holding_is_false_after_the_holding_is_sold_out():
    coordinator, _, _ = _coordinator()
    coordinator.replace_holdings([_holding()], {})

    coordinator.replace_holdings([], {})

    assert coordinator.has_holding("BTCUSDT") is False
