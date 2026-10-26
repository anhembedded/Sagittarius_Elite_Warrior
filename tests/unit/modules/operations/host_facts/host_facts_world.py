"""`EPIC-047B` - the host's facts as the tests build them: real contract types, no doubles of them."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeFacts,
    ExchangeLoaded,
    ExchangeUnavailable,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.earlier_runs_inventory import (
    EarlierRunsInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    DEFAULT_OWNER_BUDGET_CAPS,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

NOW = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
#: A value shaped like what a key or a URL carries; no test may find it in the file.
PLANTED_KEY_LIKE = "AKIA-SECRET-xK9f2LmQ7vR1"


def spot_facts(*, unavailable: str = "") -> ExchangeFacts:
    return ExchangeFacts(
        venue_title="Spot Testnet",
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        read_at=NOW - timedelta(seconds=30),
        base_free=Decimal("0.5"),
        base_locked=Decimal(0),
        quote_free=Decimal("1000.25"),
        quote_locked=Decimal(0),
        own_sell_base=Decimal(0),
        own_buy_quote=Decimal(0),
        own_open_orders=2,
        foreign_open_orders=0,
        earlier_runs=EarlierRunsInventory(unavailable=unavailable),
        can_trade=True,
    )


def facts(
    *,
    holder: str = "",
    reason: str = "",
    earlier_runs_reason: str = "",
    keys: tuple[VenueKeyState, ...] = (
        VenueKeyState(TradingVenue.SPOT_TESTNET, key_saved=True),
    ),
) -> HostHeldFacts:
    snapshot = (
        ExchangeUnavailable(reason)
        if reason
        else ExchangeLoaded(spot_facts(unavailable=earlier_runs_reason))
    )
    return HostHeldFacts(
        enabled_venues=(TradingVenue.SPOT_TESTNET,),
        venue_keys=keys,
        leases=(SymbolLease(TradingVenue.SPOT_TESTNET, "BTCUSDT", holder),),
        caps=DEFAULT_OWNER_BUDGET_CAPS,
        exchange_reads=(BotExchangeRead("aaaaaa", snapshot),),
    )


def document(
    revision: int = 1,
    held: HostHeldFacts | None = None,
    written_at: datetime = NOW,
    heartbeat_s: int = 15,
) -> HostFactsDocument:
    return HostFactsDocument(
        HostFactsHeader(revision, written_at, heartbeat_s, pid=4242),
        held if held is not None else facts(),
    )
