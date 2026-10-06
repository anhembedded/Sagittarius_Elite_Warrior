"""The market the Bots screen's tests trade in: one Spot symbol on one
venue, its filters (read by its order terms and held in the venue's metadata
cache, `EPIC-033N`), its book and its daily candles. Each port is its
verified fake or the real in-memory cache."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.symbol_order_metadata_cache import (
    InMemorySymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    candle,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_entry_terms import (
    OrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_entry_terms import (
    FakeOrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
    fake_venue_context,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

SYMBOL = "BTCUSDT"
VENUE = TradingVenue.SPOT_TESTNET
NOW = datetime(2026, 10, 4, 12, tzinfo=UTC)


def order_rules() -> SymbolOrderMetadata:
    """The symbol's filters, as the venue states them: its order terms read
    them, and its metadata cache holds them for the tables (`EPIC-033N`)."""
    return SymbolOrderMetadata(
        symbol=SYMBOL,
        status="TRADING",
        step_size=Decimal("0.00001"),
        tick_size=Decimal("0.01"),
        min_notional=Decimal(5),
        quantity_precision=None,
        price_precision=None,
        fetched_at=NOW,
    )


def terms() -> FakeOrderEntryTerms:
    entry = OrderEntryTerms(
        rules=order_rules(),
        commission=CommissionRate(SYMBOL, Decimal("0.001"), Decimal("0.001")),
    )
    book = BestBidAsk(SYMBOL, Decimal(64999), Decimal(1), Decimal(65001), Decimal(1))
    return FakeOrderEntryTerms(entry, books={SYMBOL: book})


def venue_contexts() -> FakeVenueContexts:
    """The venue, its metadata cache holding the symbol's filters, as a
    desk's order panel or the Grid's planner leaves it once read."""
    cache = InMemorySymbolOrderMetadataCache()
    cache.put(order_rules())
    return FakeVenueContexts(
        dataclasses.replace(fake_venue_context(VENUE), metadata_cache=cache)
    )


def daily_candles(days: int = 30) -> FakeHistoricalKlines:
    klines = FakeHistoricalKlines()
    klines.seed(
        [
            candle(
                SYMBOL,
                minutes=day * 1440,
                interval=TimeFrame.ONE_DAY,
                close_price=65000.0,
            )
            for day in range(days)
        ],
        MarketType.SPOT,
    )
    return klines
