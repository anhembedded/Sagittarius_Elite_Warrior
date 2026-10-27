"""`EPIC-047B` — what the host publishes of its own memory: the reads it remembers and the facts built from them."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.held_host_exchange_reads import (
    HeldHostExchangeReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.latest_exchange_reads import (
    LatestExchangeReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.latest_venue_reads import (
    LatestVenueReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.trading_host_held_facts import (
    TradingHostHeldFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.host_reads.exchange_bot_read_refresh import (
    ExchangeBotReadRefresh,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.venue_facts_by_profile import (
    VenueFactsByProfile,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_read_refresh import (
    IBotReadRefresh,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_host_exchange_reads import (
    IHostExchangeReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_host_held_facts import (
    IHostHeldFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_latest_exchange_reads import (
    ILatestExchangeReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_latest_venue_reads import (
    ILatestVenueReads,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sources import (
    IMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_key_states import (
    IVenueKeyStates,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)
from sagittarius_engine.interfaces.i_container import IContainer


def bind_host_facts(container: IContainer) -> None:
    """The reads `IVenueFacts` takes are remembered in `ILatestVenueReads` (the binding of
    `IVenueFacts` wraps its reader in `RecordedVenueFacts`); `IHostHeldFacts` is what the
    operations module writes to its file."""
    container.singleton(ILatestVenueReads, LatestVenueReads())
    container.singleton(IHostHeldFacts, _build_host_held_facts)
    # `EPIC-047H`: what the host reads again for the VPS tab, and the port that reads it.
    container.singleton(ILatestExchangeReads, LatestExchangeReads())
    container.singleton(
        IHostExchangeReads,
        lambda c: HeldHostExchangeReads(c.resolve(ILatestExchangeReads)),
    )
    container.singleton(IBotReadRefresh, _build_bot_read_refresh)


def _build_host_held_facts(container: IContainer) -> IHostHeldFacts:
    return TradingHostHeldFacts(
        container.resolve(IVenueTradingPorts),
        container.resolve(IVenueContexts),
        container.resolve(IVenueKeyStates),
        container.resolve(IBotStore),
        container.resolve(OwnerBudgetCaps),
        container.resolve(ILatestVenueReads),
    )


def _build_bot_read_refresh(container: IContainer) -> IBotReadRefresh:
    """The refresh reads beneath `RecordedVenueFacts` and records only a read that happened."""
    return ExchangeBotReadRefresh(
        container.resolve(IBotStore),
        container.resolve(VenueFactsByProfile),
        container.resolve(ICommandDispatcher),
        container.resolve(IVenueContexts),
        container.resolve(IBotClock),
        container.resolve(ILatestVenueReads),
        container.resolve(ILatestExchangeReads),
        container.resolve(IMarketDataSources),
    )
