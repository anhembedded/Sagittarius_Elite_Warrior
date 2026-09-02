"""Standalone live preview for the Trading screen (`EPIC-021I`)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.domain.trading.client_order_id import ClientOrderId
from Sagittarius_Elite_Warrior.src.domain.trading.live_position import LivePosition
from Sagittarius_Elite_Warrior.src.domain.trading.order import Order
from Sagittarius_Elite_Warrior.src.domain.trading.order_status import OrderStatus
from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.OpenOrdersTable.open_order_row import (
    build_open_order_row,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.PositionsTable.positions_row import (
    build_position_row,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.trading.trading_view import (
    TradingView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.trading.trading_view_model import (
    TradingViewModel,
)


def build_preview() -> QWidget:
    """Builds a standalone preview for the Trading screen — View +
    ViewModel only, no Presenter (mirrors `settings/preview.py`)."""
    view_model = TradingViewModel()
    view_model.set_symbol_options(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    view_model.symbol = "BTCUSDT"
    view_model.set_trading_state(True, False)
    view_model.set_status("Đã bật giao dịch.", False)
    view_model.set_session_stats(3, 2)

    view = TradingView()
    view.set_view_model(view_model)
    view.set_positions(
        [
            build_position_row(
                LivePosition(
                    symbol="BTCUSDT",
                    position_amt=Decimal("0.05"),
                    entry_price=Decimal("64000.00"),
                    mark_price=Decimal("64850.50"),
                    unrealized_pnl=Decimal("42.53"),
                    leverage=10,
                    margin_type=MarginType.CROSSED,
                    liquidation_price=None,
                    updated_at=datetime.now(UTC),
                )
            )
        ]
    )
    view.set_open_orders(
        [
            build_open_order_row(
                Order(
                    client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
                    symbol="ETHUSDT",
                    side=OrderSide.SELL,
                    order_type=OrderType.LIMIT,
                    quantity=Decimal("1.2"),
                    status=OrderStatus.NEW,
                    price=Decimal("3455.00"),
                )
            )
        ]
    )
    view.resize(1200, 760)
    return view
