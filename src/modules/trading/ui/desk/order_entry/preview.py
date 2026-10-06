"""Standalone preview of the order-entry panel (`ui-presentation-rule.md`
§5): the Spot desk's two columns on `BTCUSDT`, without an exchange.

The Buy side has a limit price and an amount typed, so its total, fee and
maximum show, the maximum capped by the app's 500 USDT per-order limit
(`EPIC-028O`); the Sell side holds a little BTC and has nothing typed, so it
shows "Enter an amount" and a disabled button. A stop price and a market
total are typed too, so the Stop-limit and Market tabs show them filled.

`EPIC-028I` adds a Futures tab: 10× cross, a long typed with TP/SL on, so
the cost, the liquidation estimate and the TP and SL fields show."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from PySide6.QtWidgets import QCheckBox, QTabWidget, QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBracket,
    LeverageBrackets,
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
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.futures_entry_context import (
    FuturesEntryContext,
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
    view_model.presenter_side().begin_symbol("BTCUSDT")
    view_model.presenter_side().set_context(
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
    view_model.presenter_side().set_last_price(Decimal("60123.45"))
    view_model.intents.set_price(EntrySide.BUY, "60000")
    view_model.intents.set_quantity(EntrySide.BUY, "0.005")
    view_model.intents.use_last_price(EntrySide.SELL)
    view_model.intents.set_stop_price(EntrySide.BUY, "60500")
    view_model.intents.set_total(EntrySide.BUY, "250")
    tabs = QTabWidget()
    tabs.addTab(OrderEntryPanel(view_model), "Spot")
    tabs.addTab(_futures_panel(), "Futures")
    tabs.setWindowTitle("Order entry")
    return tabs


def _futures_panel() -> QWidget:
    setting = FuturesSymbolSetting(
        "BTCUSDT", 10, MarginType.CROSSED, Decimal(2_000_000)
    )
    view_model = OrderEntryViewModel(desk_profile_for(TradingVenue.FUTURES_TESTNET))
    view_model.presenter_side().begin_symbol("BTCUSDT")
    view_model.presenter_side().set_context(
        OrderEntryContext(
            symbol="BTCUSDT",
            base_asset="BTC",
            quote_asset="USDT",
            terms=PREVIEW_TERMS,
            available_quote=Decimal("1234.56"),
            free_base=None,
            notional_limit=Decimal(5000),
            futures=FuturesEntryContext(
                setting=setting,
                brackets=LeverageBrackets(
                    "BTCUSDT",
                    (
                        LeverageBracket(
                            1,
                            125,
                            Decimal(0),
                            Decimal(10**7),
                            Decimal("0.004"),
                            Decimal(0),
                        ),
                    ),
                ),
                mark_price=Decimal("60110.20"),
                book=None,
                position_amount=Decimal(0),
                wallet_balance=Decimal(500),
            ),
        )
    )
    view_model.options.show_setting(setting)
    view_model.presenter_side().set_last_price(Decimal("60123.45"))
    view_model.intents.set_price(EntrySide.BUY, "60000")
    view_model.intents.set_quantity(EntrySide.BUY, "0.05")
    view_model.options.set_tp_sl_enabled(True)
    view_model.options.set_take_profit(EntrySide.BUY, "63000")
    view_model.options.set_stop_loss(EntrySide.BUY, "58500")
    panel = OrderEntryPanel(view_model)
    tp_sl = panel.findChild(QCheckBox, "chkTpSl")
    if tp_sl is not None:
        tp_sl.setChecked(True)
    return panel
