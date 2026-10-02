"""Standalone live preview for the Trading screen (`EPIC-021I`)."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
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
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_view_model import (
    DeskViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.holding_row import (
    build_holding_row,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.open_order_row import (
    build_open_order_row,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trading.trading_view import (
    TradingView,
)


def build_preview() -> QWidget:
    """Builds a standalone preview for the Trading screen — View +
    ViewModel only, no Presenter (mirrors `settings/preview.py`).

    `EPIC-027O` — Spot: the Holdings panel replaces Positions, leverage is
    hidden, and the manual-order buttons read BUY/SELL. Futures' own
    Positions/leverage/LONG-SHORT preview lives in `dev_board`'s own
    `preview.py`, so this file does not need to show both venues."""
    view_model = DeskViewModel()
    view_model.set_symbol_options(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    view_model.symbol = "BTCUSDT"
    view_model.set_trading_state(True, False)
    view_model.set_status("Trading enabled.", False)
    view_model.set_session_stats(3, 2)

    view = TradingView(market_type=MarketType.SPOT)
    view.set_view_model(view_model)
    view.set_holdings(
        [
            build_holding_row(
                SpotHolding(
                    asset="BTC",
                    free=Decimal("0.05"),
                    locked=Decimal("0.0"),
                    dust_threshold=Decimal("0.0001"),
                ),
                {"BTC": Decimal("64850.50")},
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
