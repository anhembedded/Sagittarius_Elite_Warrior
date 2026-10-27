"""`EPIC-047C` - instances of the host-facts document, a full one and a minimal one."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeLoaded,
    ExchangeUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_reads import (
    BotFillsRead,
    BotPlannerRead,
    HostExchangeReads,
    SymbolRulesRead,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    FuturesLoaded,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_held_facts import (
    BotExchangeRead,
    HostHeldFacts,
    SymbolLease,
    VenueKeyState,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    HostFactsDocument,
    HostFactsHeader,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_reads_document import (
    HostReadsDocument,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.market_data_document import (
    FormingCandle,
    MarketDataDocument,
    SymbolMarket,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    PercentPriceBand,
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_bots import (
    full_exchange_facts,
    full_fills,
    full_futures_facts,
    full_planner_market,
    minimal_fills,
    minimal_planner_market_unpriced,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_trading import (
    full_budget_caps,
    minimal_budget_caps,
)

WRITTEN = datetime(2026, 10, 26, 12, 0, 5, tzinfo=UTC)


def full_host_facts() -> HostFactsDocument:
    return HostFactsDocument(
        HostFactsHeader(41, WRITTEN, 15, pid=4242),
        HostHeldFacts(
            enabled_venues=(TradingVenue.SPOT_TESTNET, TradingVenue.FUTURES_TESTNET),
            venue_keys=(
                VenueKeyState(TradingVenue.SPOT_TESTNET, key_saved=True),
                VenueKeyState(TradingVenue.FUTURES_TESTNET, key_saved=False),
            ),
            leases=(
                SymbolLease(TradingVenue.SPOT_TESTNET, "BTCUSDT", "grid:b-0001"),
                SymbolLease(TradingVenue.FUTURES_TESTNET, "BTCUSDT", ""),
            ),
            caps=full_budget_caps(),
            exchange_reads=(
                BotExchangeRead("b-0001", ExchangeLoaded(full_exchange_facts())),
                BotExchangeRead("b-0002", FuturesLoaded(full_futures_facts())),
                BotExchangeRead(
                    "b-0003", ExchangeUnavailable("the host could not read")
                ),
            ),
        ),
    )


def minimal_host_facts() -> HostFactsDocument:
    return HostFactsDocument(
        HostFactsHeader(1, WRITTEN, 15, pid=1),
        HostHeldFacts(
            enabled_venues=(),
            venue_keys=(),
            leases=(),
            caps=minimal_budget_caps(),
        ),
    )


def _candle(timeframe: str, *, complete: bool) -> FormingCandle:
    return FormingCandle(
        timeframe,
        WRITTEN.replace(second=0),
        Decimal("67000.5"),
        Decimal(67100),
        Decimal("66950.25"),
        Decimal("67050.75"),
        Decimal("12.345"),
        complete,
    )


def full_market_data() -> MarketDataDocument:
    return MarketDataDocument(
        HostFactsHeader(77, WRITTEN, 5, pid=4242),
        (
            SymbolMarket(
                TradingVenue.FUTURES_TESTNET,
                "BTCUSDT",
                last_price=Decimal("67050.75"),
                last_at=WRITTEN,
                mark_price=Decimal("67049.9"),
                mark_at=WRITTEN,
                forming=(_candle("1m", complete=True), _candle("1h", complete=False)),
            ),
            SymbolMarket(TradingVenue.SPOT_TESTNET, "ETHUSDT"),
        ),
    )


def minimal_market_data() -> MarketDataDocument:
    return MarketDataDocument(HostFactsHeader(1, WRITTEN, 5, pid=1))


def full_host_reads() -> HostReadsDocument:
    return HostReadsDocument(
        HostFactsHeader(9, WRITTEN, 30, pid=4242),
        HostExchangeReads(
            planner=(
                BotPlannerRead("b-0001", WRITTEN, full_planner_market()),
                BotPlannerRead("b-0002", WRITTEN, minimal_planner_market_unpriced()),
            ),
            fills=(
                BotFillsRead("b-0001", WRITTEN, full_fills()),
                BotFillsRead("b-0002", WRITTEN, minimal_fills()),
            ),
            symbol_rules=(
                SymbolRulesRead(
                    TradingVenue.SPOT_TESTNET,
                    "BTCUSDT",
                    WRITTEN,
                    SymbolOrderMetadata(
                        "BTCUSDT",
                        "TRADING",
                        Decimal("0.00001"),
                        Decimal("0.01"),
                        Decimal(5),
                        5,
                        2,
                        WRITTEN,
                        market_step_size=Decimal("0.00001"),
                        price_band=PercentPriceBand(
                            Decimal("0.2"), Decimal(5), Decimal("0.2"), Decimal(5)
                        ),
                    ),
                ),
            ),
        ),
    )


def minimal_host_reads() -> HostReadsDocument:
    return HostReadsDocument(
        HostFactsHeader(1, WRITTEN, 30, pid=1), HostExchangeReads()
    )
