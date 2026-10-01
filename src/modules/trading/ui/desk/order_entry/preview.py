"""Standalone preview of the order-entry panel (`ui-presentation-rule.md`
§5): the Spot desk's two columns on `BTCUSDT`, without an exchange.

The Buy side has a limit price and an amount typed, so its total, fee and
maximum show, the maximum capped by the app's 500 USDT per-order limit
(`EPIC-028O`); the Sell side holds a little BTC and has nothing typed, so it
shows "Enter an amount" and a disabled button. A stop price and a market
total are typed too, so the Stop-limit and Market tabs show them filled."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_entry_terms import (
    OrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    desk_profile_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_panel import (
    OrderEntryPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
    OrderEntryContext,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_view_model import (
    OrderEntryViewModel,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

PREVIEW_TERMS = OrderEntryTerms(
    rules=SymbolOrderMetadata(
        symbol="BTCUSDT",
        status="TRADING",
        step_size=Decimal("0.00001"),
        tick_size=Decimal("0.01"),
        min_notional=Decimal(5),
        quantity_precision=None,
        price_precision=None,
        fetched_at=datetime(2026, 9, 30, tzinfo=UTC),
    ),
    commission=CommissionRate(
        symbol="BTCUSDT", maker=Decimal("0.001"), taker=Decimal("0.001")
    ),
)


def build_preview() -> QWidget:
    view_model = OrderEntryViewModel(desk_profile_for(TradingVenue.SPOT_TESTNET))
    view_model.begin_symbol("BTCUSDT")
    view_model.set_context(
        OrderEntryContext(
            symbol="BTCUSDT",
            base_asset="BTC",
            quote_asset="USDT",
            terms=PREVIEW_TERMS,
            available_quote=Decimal("1234.56"),
            free_base=Decimal("0.0213"),
            notional_limit=Decimal(500),
        )
    )
    view_model.set_last_price(Decimal("60123.45"))
    view_model.set_price(EntrySide.BUY, "60000")
    view_model.set_quantity(EntrySide.BUY, "0.005")
    view_model.use_last_price(EntrySide.SELL)
    view_model.set_stop_price(EntrySide.BUY, "60500")
    view_model.set_total(EntrySide.BUY, "250")
    panel = OrderEntryPanel(view_model)
    panel.setWindowTitle("Order entry — Spot")
    return panel
