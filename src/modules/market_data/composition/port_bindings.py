"""market_data's **published** ports: what another context may depend on.

The fourth binding table, and the one with a different audience from the other
three. `adapter_bindings.py` answers "which class talks to SQLite / Binance",
`command_bindings.py` and `query_bindings.py` are this module's internal
routing table. Everything in all three is *inward*: nobody outside the module
resolves a `SyncMarketDataCommandHandler`, and the boundary guard fails if they
try.

This table is *outward*. Every entry is a port declared in `contracts/` that a
consumer in another context resolves by name — so it changes when the module's
published API changes, which is a different reason from the other three and
therefore a different file (`architecture-rule.md` §5 rule 5: does changing A
force you to read B? swapping SQLite does not touch what the app may ask
market_data to do).

`singleton`, unlike the transient command handlers: a published port is a
stateless façade over a dispatch, so one instance answers every consumer, and a
consumer that holds it for a screen's lifetime — which is what a Presenter
does — holds nothing that another screen's sync could corrupt.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.symbol_metadata_provider import (
    BinanceSymbolMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.market_data_sources import (
    MarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.list_available_symbols import (
    SymbolCatalogService,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sources import (
    IMarketDataSources,
    MarketDataPorts,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_venues import (
    IMarketDataVenues,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_range_coverage import (
    IRangeCoverage,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog import (
    ISymbolCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog_repository import (
    ISymbolCatalogRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_market_metadata_cache import (
    ISymbolMarketMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_metadata_provider import (
    ISymbolMetadataProvider,
)
from sagittarius_engine.interfaces.i_container import IContainer


def bind_published_ports(container: IContainer) -> None:
    """Register the ports other bounded contexts are allowed to resolve.

    `BUG-172`: `IMarketDataSources` is the port of a screen that acts on a
    venue — it asks for that venue's four ports. The four bound below are the
    default venue's (the public mainnet), for the screens that act on
    none (Data mode, a plain historical backtest, the CLI): the same objects as
    `ports_for(default)`, so a stream owner and its sync agree wherever each was
    resolved from."""
    container.singleton(IMarketDataSources, _build_market_data_sources)
    container.singleton(IMarketDataSync, _build_market_data_sync)
    container.singleton(IHistoricalKlines, _build_historical_klines)
    container.singleton(IMarketStream, _build_market_stream)
    container.singleton(ISymbolCatalog, _build_symbol_catalog)
    container.singleton(IRangeCoverage, _build_range_coverage)
    container.singleton(ISymbolMetadataProvider, _build_symbol_metadata_provider)


def _build_market_data_sources(container: IContainer) -> IMarketDataSources:
    """A named factory rather than a lambda, matching `adapter_bindings.py`:
    the `resolve()` must happen when something first asks for the port, never
    during `register()` — `shell/registering_container.py` raises if a module
    resolves while registering, and `ICommandDispatcher` is itself bound by
    another part of the boot."""
    return MarketDataSources(
        container.resolve(ICommandDispatcher), container.resolve(IMarketDataVenues)
    )


def _default_ports(container: IContainer) -> MarketDataPorts:
    sources = container.resolve(IMarketDataSources)
    return sources.ports_for(sources.default_venue)


def _build_market_data_sync(container: IContainer) -> IMarketDataSync:
    """The default venue's sync (`BUG-172`): a sync dispatches the module's own
    command, so the in-flight guard and the progress events stay on one path."""
    return _default_ports(container).sync


def _build_historical_klines(container: IContainer) -> IHistoricalKlines:
    """The default venue's reader, per HLD §3.4: "a port implementation may be
    the existing handler" — no pass-through object and no extra file, which is
    the accidental complexity ADR D2 exists to avoid. One class, one reader per
    venue (`MarketDataSources`), stateless but for the store it reads."""
    return _default_ports(container).history


def _build_market_stream(container: IContainer) -> IMarketStream:
    """The default venue's stream, which dispatches the module's two stream
    commands for the reason `market_stream_service.py` records: the module's
    own CLI dispatches them too, and a port that reached past them to
    `ILiveStreamService` would give the CLI and the screens two paths to one
    websocket."""
    return _default_ports(container).stream


def _build_symbol_catalog(container: IContainer) -> ISymbolCatalog:
    """The service itself, per HLD §3.4 — the same "no pass-through object"
    rule `_build_historical_klines` above records.

    It holds two of the module's own ports rather than dispatching, because
    unlike the sync and the stream there is no command in the middle: the
    class *is* the read. `IExchangeClient` is resolved lazily here for the
    reason `module.py` documents — constructing one is a network call
    (`BUG-045`), so a session that never opens a symbol picker never builds
    it.
    """
    return SymbolCatalogService(
        lambda: container.resolve(IExchangeClient),
        container.resolve(ISymbolCatalogRepository),
    )


def _build_range_coverage(container: IContainer) -> IRangeCoverage:
    """The default venue's coverage check, reading the same store
    `IHistoricalKlines` reads."""
    return _default_ports(container).coverage


def _build_symbol_metadata_provider(container: IContainer) -> ISymbolMetadataProvider:
    """`BUG-127` — the wire that was missing, and the reason it is a *provider*.

    `ISymbolMarketMetadataCache` is a store; something has to fill it, and for
    two epics nothing did — `parse_binance_symbol_metadata()`, the only producer
    of a `SymbolMarketMetadata` anywhere, had no caller in `src/` at all. This
    binds the object that closes that gap.

    The client is resolved **lazily**, exactly as `_build_symbol_catalog` above
    resolves it and for the same reason: constructing `PythonBinanceClient` is a
    network call (`BUG-045`), and three Presenters resolve this module's ports
    while they are being built, so a session that never opens the Backtest
    screen must never build one.
    """
    return BinanceSymbolMetadataProvider(
        lambda: container.resolve(IExchangeClient),
        container.resolve(ISymbolMarketMetadataCache),
    )
