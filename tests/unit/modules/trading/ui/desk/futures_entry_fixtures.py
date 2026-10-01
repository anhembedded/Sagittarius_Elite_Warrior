"""`EPIC-028I` — a Futures `BTCUSDT` context the Futures panel tests share:
10× cross, a 1 000 000 notional cap, the mark at 60 000 and a one-tick book
around it, flat unless a test says otherwise."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    FuturesAccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
    MarginType,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBracket,
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.mark_price import MarkPrice
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_entry_terms import (
    FakeOrderEntryTerms,
    FuturesReads,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.futures_entry_context import (
    FuturesEntryContext,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    OrderEntryContext,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .order_entry_fixtures import TERMS, spot_context

MARK = Decimal(60000)
NOW = datetime(2026, 10, 1, tzinfo=UTC)

BRACKETS = LeverageBrackets(
    symbol="BTCUSDT",
    brackets=(
        LeverageBracket(
            bracket=1,
            initial_leverage=125,
            notional_floor=Decimal(0),
            notional_cap=Decimal(50000),
            maintenance_margin_rate=Decimal("0.004"),
            maintenance_amount=Decimal(0),
        ),
        LeverageBracket(
            bracket=2,
            initial_leverage=100,
            notional_floor=Decimal(50000),
            notional_cap=Decimal(10_000_000),
            maintenance_margin_rate=Decimal("0.005"),
            maintenance_amount=Decimal(50),
        ),
    ),
)


def futures_reads(
    *,
    leverage: int = 10,
    margin_type: MarginType = MarginType.CROSSED,
    max_notional: Decimal = Decimal(1_000_000),
    position: Decimal = Decimal(0),
    book: BestBidAsk | None = None,
    wallet: Decimal | None = Decimal(1000),
) -> FuturesEntryContext:
    return FuturesEntryContext(
        setting=FuturesSymbolSetting("BTCUSDT", leverage, margin_type, max_notional),
        brackets=BRACKETS,
        mark_price=MARK,
        book=book
        or BestBidAsk(
            "BTCUSDT",
            MARK - Decimal("0.1"),
            Decimal(1),
            MARK + Decimal("0.1"),
            Decimal(1),
        ),
        position_amount=position,
        wallet_balance=wallet,
    )


def futures_context(
    available: Decimal | None = Decimal(1000),
    reads: FuturesEntryContext | None = None,
    notional_limit: Decimal | None = None,
) -> OrderEntryContext:
    """The Spot fixture's filters and fees, with Futures reads attached."""
    return replace(
        spot_context(available_quote=available, notional_limit=notional_limit),
        futures=reads or futures_reads(),
        free_base=None,
    )


def futures_status(available: Decimal = Decimal(1000)) -> ExchangeConnectionStatus:
    """A reachable one-way Futures account with `available` USDT to spend."""
    return ExchangeConnectionStatus(
        venue=TradingVenue.FUTURES_TESTNET,
        reachable=True,
        failure=None,
        server_time_skew_ms=0,
        usdt_balance=available,
        position_mode=PositionMode.ONE_WAY,
        margin_type=None,
        open_position_count=0,
        summary=FuturesAccountSummary(
            venue=TradingVenue.FUTURES_TESTNET,
            available_balance=available,
            equity=available,
            wallet_balance=available,
            margin_balance=available,
            unrealized_pnl=Decimal(0),
            position_mode=PositionMode.ONE_WAY,
        ),
    )


def futures_terms(setting: FuturesSymbolSetting | None = None) -> FakeOrderEntryTerms:
    """The fake's answers for a Futures `BTCUSDT`: 10× cross, the mark at
    `MARK`, a one-tick book and a 5 000 USDT per-order limit."""
    return FakeOrderEntryTerms(
        TERMS,
        futures=FuturesReads(
            settings={
                "BTCUSDT": setting
                or FuturesSymbolSetting(
                    "BTCUSDT", 10, MarginType.CROSSED, Decimal(1_000_000)
                )
            },
            brackets={"BTCUSDT": BRACKETS},
            marks={"BTCUSDT": MarkPrice("BTCUSDT", MARK, NOW)},
        ),
        notional_limit=Decimal(5000),
        books={
            "BTCUSDT": BestBidAsk(
                "BTCUSDT",
                MARK - Decimal("0.1"),
                Decimal(1),
                MARK + Decimal("0.1"),
                Decimal(1),
            )
        },
    )
