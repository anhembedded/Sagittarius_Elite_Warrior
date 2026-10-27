"""`EPIC-047C` - instances of the host-facts document, a full one and a minimal one."""

from __future__ import annotations

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeLoaded,
    ExchangeUnavailable,
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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_bots import (
    full_exchange_facts,
    full_futures_facts,
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
