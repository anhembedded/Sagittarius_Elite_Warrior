# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.domain.trading.client_order_id import ClientOrderId
from Sagittarius_Elite_Warrior.src.domain.trading.order import Order
from Sagittarius_Elite_Warrior.src.domain.trading.order_status import OrderStatus
from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.OpenOrdersTable.open_order_row import (
    build_open_order_row,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.OpenOrdersTable.open_orders_vm import (
    OpenOrdersVM,
)


def _order(
    symbol="BTCUSDT",
    side=OrderSide.BUY,
    order_type=OrderType.LIMIT,
    price="63000.00",
) -> Order:
    return Order(
        client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=Decimal("0.5"),
        status=OrderStatus.NEW,
        price=Decimal(price) if price is not None else None,
    )


def test_starts_empty() -> None:
    assert OpenOrdersVM().rows == []


def test_set_rows_projects_every_field() -> None:
    vm = OpenOrdersVM()
    vm.set_rows([build_open_order_row(_order())])

    (row,) = vm.rows
    assert row["symbol"] == "BTCUSDT"
    assert row["sideLabel"] == "BUY"
    assert row["sideIsBuy"] is True
    assert row["orderTypeText"] == "LIMIT"
    assert row["quantityText"] == "0.5000"
    assert row["priceText"] == "63,000.00"
    assert row["statusText"] == "NEW"


def test_sell_side_is_not_buy() -> None:
    vm = OpenOrdersVM()
    vm.set_rows([build_open_order_row(_order(side=OrderSide.SELL))])

    assert vm.rows[0]["sideIsBuy"] is False
    assert vm.rows[0]["sideLabel"] == "SELL"


def test_market_order_with_no_price_renders_a_placeholder() -> None:
    vm = OpenOrdersVM()
    vm.set_rows([build_open_order_row(_order(order_type=OrderType.MARKET, price=None))])

    assert vm.rows[0]["priceText"] == "—"


def test_set_rows_replaces_the_previous_set() -> None:
    vm = OpenOrdersVM()
    vm.set_rows([build_open_order_row(_order(symbol="BTCUSDT"))])
    vm.set_rows([build_open_order_row(_order(symbol="ETHUSDT"))])

    assert len(vm.rows) == 1
    assert vm.rows[0]["symbol"] == "ETHUSDT"
