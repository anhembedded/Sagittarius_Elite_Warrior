"""Standalone live preview for `OpenOrdersTable.qml` (`EPIC-021I`)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.domain.order import Order
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import StyleRole
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.embed import QuickSurface
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.OpenOrdersTable.open_order_row import (
    build_open_order_row,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.OpenOrdersTable.open_orders_vm import (
    OpenOrdersVM,
)

_QML_FILE = Path(__file__).with_name("OpenOrdersTable.qml")

_SAMPLE_ORDERS = [
    Order(
        client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.05"),
        status=OrderStatus.NEW,
        price=Decimal("63000.00"),
    ),
    Order(
        client_order_id=ClientOrderId("SEW-b02e5d83f1c9"),
        symbol="ETHUSDT",
        side=OrderSide.SELL,
        order_type=OrderType.STOP_MARKET,
        quantity=Decimal("1.2"),
        status=OrderStatus.NEW,
        stop_price=Decimal("3300.00"),
    ),
]


def build_preview() -> QWidget:
    """Builds the OpenOrdersTable preview, no host chrome."""
    vm = OpenOrdersVM()
    vm.set_rows([build_open_order_row(order) for order in _SAMPLE_ORDERS])

    surface = QuickSurface(
        _QML_FILE,
        surface=StyleRole.SURFACE,
        context={"vm": vm},
        object_name="openOrdersTablePreview",
    )
    surface.resize(760, 320)
    return surface
