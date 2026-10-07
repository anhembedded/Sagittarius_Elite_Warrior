"""Which concrete class answers each of market_data's ports.

One function, called from `MarketDataModule.register()`. It is a separate file
from the command and query bindings because the three change for different
reasons: swapping SQLite for something else touches only this file, adding a
query touches only `query_bindings.py`. Rule 5 of `architecture-rule.md` §5 —
*does changing A force you to read B?* — answers no in both directions.

**Every binding here is lazy, and that is not a style choice.** `register()` may
not call `resolve()` (`shell/registering_container.py` raises if it does), and
two of these adapters do real work in their constructor: `DatabaseManager`
creates the SQLite directory, and `python-binance`'s `Client()` pings the
network (`BUG-045`). Passing the class, or a factory taking the container, means
nothing runs until something actually asks for the port — so importing this
module, or booting with no database configured, costs nothing.
"""

from __future__ import annotations

import os

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.repo_root import data_root_override
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.binance_websocket_service import (
    BinanceWebsocketService,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.market_data_session_factory import (
    MarketDataSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.live_stream_adapter import (
    LiveStreamEngineAdapter,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.database_manager import (
    DatabaseConfig,
    DatabaseManager,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.json_symbol_catalog_repository import (
    JsonSymbolCatalogRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.sqlalchemy_repository import (
    SQLAlchemyMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.symbol_market_metadata_cache import (
    InMemorySymbolMarketMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.venue_directory import (
    venue_directory,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.sync.in_flight_sync_guard import (
    InFlightSyncGuard,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.composition.database_directory import (
    database_directory,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.composition.market_data_venues import (
    MarketDataVenues,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_session_factory import (
    IExchangeSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_live_stream_service import (
    ILiveStreamService,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_venues import (
    IMarketDataVenues,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog_repository import (
    ISymbolCatalogRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_market_metadata_cache import (
    ISymbolMarketMetadataCache,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_endpoints import (
    resolve_market_data_venue,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_container import IContainer


def bind_adapters(container: IContainer) -> None:
    """Bind this context's ports to the adapters that implement them."""
    # `EPIC-025E` PR 4.4f-3: the last two bindings the legacy composition root
    # still held for this module — `MarketDataVenue` before `IExchangeSessionFactory`
    # since the latter's factory needs the former resolved first.
    container.singleton(MarketDataVenue, _build_market_data_venue)
    container.singleton(IExchangeSessionFactory, _build_exchange_session_factory)

    container.singleton(DatabaseConfig, _build_database_config)
    container.singleton(IMarketDataVenues, _build_market_data_venues)
    container.singleton(DatabaseManager, _build_database_manager)
    container.singleton(IMarketDataRepository, SQLAlchemyMarketDataRepository)
    container.singleton(ISymbolCatalogRepository, JsonSymbolCatalogRepository)
    # `BUG-127` — the store the Backtest screen's exchange-rule check reads.
    # It was written in `BOT-095E1` and bound by **nobody** for two epics, so
    # `container.resolve()` raised, the presenter's `except` built a private
    # empty one, and the check answered "not verified" for every symbol from
    # the day it shipped. A `singleton`, not `bind()`: the sync warms it on a
    # worker thread and the screen reads it on the main thread, and two
    # instances would mean the reader never sees the write.
    container.singleton(ISymbolMarketMetadataCache, InMemorySymbolMarketMetadataCache)
    container.singleton(ILiveStreamService, BinanceWebsocketService)
    container.singleton(IExchangeClient, _build_exchange_client)

    # `BOT-121`: a singleton, never `bind()` — a sync started from Backtest and
    # one started from Data Management must see each other's in-flight
    # `(symbol, interval)` keys, and a transient guard would give each caller
    # its own empty registry, which excludes nothing.
    container.singleton(InFlightSyncGuard, InFlightSyncGuard)

    # Transient: the adapter wraps one live stream's callbacks, so a second
    # stream needs a second adapter. Nothing shares it.
    container.bind(LiveStreamEngineAdapter, LiveStreamEngineAdapter)


def _build_market_data_venue(container: IContainer) -> MarketDataVenue:
    """`EPIC-021A`: registered as its own singleton so `BinanceWebsocketService`'s
    constructor (which needs it for the testnet flag) picks up the real
    configured value via auto-wiring — not its own default fallback, which
    would silently pin every install to MAINNET_PUBLIC regardless of config."""
    return resolve_market_data_venue(container.resolve(IConfig))


def _build_market_data_venues(container: IContainer) -> IMarketDataVenues:
    """`BUG-172`: the registry of each venue's store, client and stream; the
    default venue is the container's own bindings below."""
    return MarketDataVenues(
        container,
        container.resolve(DatabaseConfig),
        container.resolve(MarketDataVenue),
    )


def _build_exchange_session_factory(container: IContainer) -> IExchangeSessionFactory:
    """`EPIC-025` PR 1.3c-4 — one factory per bounded context, where there
    used to be one instance answering both. This module's own adapter; the
    SDK session behind it still comes from `support/binance_gateway`, the
    only place allowed to construct a `python-binance` `Client`."""
    return MarketDataSessionFactory(container.resolve(MarketDataVenue))


def _build_database_config(container: IContainer) -> DatabaseConfig:
    """`database_directory.py` owns the precedence of `database.dir`,
    `SEW_DATA_ROOT` and the working directory."""
    configured = container.resolve(IConfig).get(ConfigKeys.DATABASE_DIR.value)
    return DatabaseConfig(
        db_dir=database_directory(
            str(configured) if configured else None,
            data_root_override(),
            os.getcwd(),
        )
    )


def _build_database_manager(container: IContainer) -> DatabaseManager:
    """`EPIC-027A` — migrate once, right after construction and before any
    shard is opened (`DatabaseManager.migrate_legacy_shards()`'s own
    precondition), so a pre-existing install's shards are tagged Spot (ADR
    O3) before the first read or sync ever asks for a market.

    `BUG-172`: the manager of the *default* venue — `exchange.market_data_venue`,
    for the screens that act on no venue — whose shards sit in that venue's own
    directory (`venue_directory`). The other venues' managers are built by
    `MarketDataVenues`."""
    base = container.resolve(DatabaseConfig)
    venue = container.resolve(MarketDataVenue)
    manager = DatabaseManager(
        DatabaseConfig(db_dir=venue_directory(base.db_dir, venue))
    )
    if venue is MarketDataVenue.MAINNET_PUBLIC:
        # Only the mainnet's shards can be legacy ones: every pre-`EPIC-027A`
        # shard was downloaded from the mainnet (ADR O3).
        manager.migrate_legacy_shards()
    return manager


def _build_exchange_client(container: IContainer) -> IExchangeClient:
    """The session factory decides the venue; this module only asks for a
    market-data client. Both `MarketDataVenue` and `IExchangeSessionFactory`
    are bound above, in this same file (`EPIC-025E` PR 4.4f-3 moved them out
    of the legacy composition root, `binance_bot_module.py`)."""
    return container.resolve(IExchangeSessionFactory).create_market_data_client()
