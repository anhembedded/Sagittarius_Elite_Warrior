"""`EPIC-047B` — what the host publishes of its own memory: the reads it remembers and the facts built from them."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.adapters.latest_venue_reads import (
    LatestVenueReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.trading_host_held_facts import (
    TradingHostHeldFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_host_held_facts import (
    IHostHeldFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_latest_venue_reads import (
    ILatestVenueReads,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
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


def _build_host_held_facts(container: IContainer) -> IHostHeldFacts:
    return TradingHostHeldFacts(
        container.resolve(IVenueTradingPorts),
        container.resolve(IVenueContexts),
        container.resolve(IBotStore),
        container.resolve(OwnerBudgetCaps),
        container.resolve(ILatestVenueReads),
    )
