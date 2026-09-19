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
from Sagittarius_Elite_Warrior.src.modules.market_data.application.sync.in_flight_sync_guard import (
    InFlightSyncGuard,
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

#: Where the per-symbol SQLite shards go when `database.dir` says nothing —
#: `./database` relative to the working directory, which is what every existing
#: install already has on disk.
_DEFAULT_DB_DIR_NAME = "database"


def bind_adapters(container: IContainer) -> None:
    """Bind this context's ports to the adapters that implement them."""
    # `EPIC-025E` PR 4.4f-3: the last two bindings the legacy composition root
    # still held for this module — `MarketDataVenue` before `IExchangeSessionFactory`
    # since the latter's factory needs the former resolved first.
    container.singleton(MarketDataVenue, _build_market_data_venue)
    container.singleton(IExchangeSessionFactory, _build_exchange_session_factory)

    container.singleton(DatabaseConfig, _build_database_config)
    container.singleton(DatabaseManager, DatabaseManager)
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


def _build_exchange_session_factory(container: IContainer) -> IExchangeSessionFactory:
    """`EPIC-025` PR 1.3c-4 — one factory per bounded context, where there
    used to be one instance answering both. This module's own adapter; the
    SDK session behind it still comes from `support/binance_gateway`, the
    only place allowed to construct a `python-binance` `Client`."""
    return MarketDataSessionFactory(container.resolve(MarketDataVenue))


def _build_database_config(container: IContainer) -> DatabaseConfig:
    config = container.resolve(IConfig)
    db_dir = config.get(ConfigKeys.DATABASE_DIR.value) or os.path.join(
        os.getcwd(), _DEFAULT_DB_DIR_NAME
    )
    return DatabaseConfig(db_dir=db_dir)


def _build_exchange_client(container: IContainer) -> IExchangeClient:
    """The session factory decides the venue; this module only asks for a
    market-data client. Both `MarketDataVenue` and `IExchangeSessionFactory`
    are bound above, in this same file (`EPIC-025E` PR 4.4f-3 moved them out
    of the legacy composition root, `binance_bot_module.py`)."""
    return container.resolve(IExchangeSessionFactory).create_market_data_client()
