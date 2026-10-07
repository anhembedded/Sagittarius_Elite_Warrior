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
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sources import (
    IMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    candle,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_repository import (
    FakeMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sources import (
    FakeMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sync import (
    FakeMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_credentials_provider import (
    FakeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_entry_terms import (
    FakeOrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
    fake_venue_context,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.interfaces.i_container import IContainer

SYMBOL = "BTCUSDT"
VENUE = TradingVenue.SPOT_TESTNET
#: The other Spot venue a draft bot may be moved to (`BOT-171`).
MAINNET = TradingVenue.SPOT_MAINNET
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


def venue_contexts(mainnet_key: bool = True) -> FakeVenueContexts:
    """Each Spot venue, its metadata cache holding the symbol's filters, as a
    desk's order panel or the Grid's planner leaves it once read; the testnet
    has an API key saved, the mainnet one when `mainnet_key`."""
    return FakeVenueContexts(
        _venue_context(VENUE, has_key=True),
        _venue_context(MAINNET, has_key=mainnet_key),
    )


def _venue_context(venue: TradingVenue, *, has_key: bool):
    cache = InMemorySymbolOrderMetadataCache()
    cache.put(order_rules())
    return dataclasses.replace(
        fake_venue_context(
            venue, credentials_provider=FakeCredentialsProvider(has_key=has_key)
        ),
        metadata_cache=cache,
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


def register_market_data(
    container: IContainer, venue: MarketDataVenue
) -> FakeMarketDataSources:
    """The market data of each venue's bots, each port its verified fake: the
    default ports and the venue's own (`BUG-172`: a bot reads the market of the
    venue it trades on, through `IMarketDataSources`). The public mainnet, where
    Spot Mainnet bots read, has ports of its own, so a test can tell which
    market a chart read (`BOT-171`)."""
    history, sync = daily_candles(), FakeMarketDataSync()
    repository, stream = FakeMarketDataRepository(), FakeMarketStream()
    container.singleton(IHistoricalKlines, history)
    container.singleton(IMarketDataSync, sync)
    container.singleton(IMarketDataRepository, repository)
    container.singleton(IMarketStream, stream)
    sources = FakeMarketDataSources().serving(
        FakeMarketDataSources.ports(
            venue,
            sync=sync,
            history=history,
            stream=stream,
            repository=repository,
        )
    )
    sources.serving(
        FakeMarketDataSources.ports(MAINNET.market_data_venue, history=daily_candles())
    )
    container.singleton(IMarketDataSources, sources)
    return sources
