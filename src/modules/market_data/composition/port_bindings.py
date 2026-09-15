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
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.get_backtest_range_coverage import (
    RangeCoverageService,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.get_historical_klines import (
    StoredKlinesReader,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.list_available_symbols import (
    SymbolCatalogService,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.market_stream_service import (
    MarketStreamService,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.sync.market_data_sync_service import (
    MarketDataSyncService,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
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
from sagittarius_engine.interfaces.i_container import IContainer


def bind_published_ports(container: IContainer) -> None:
    """Register the ports other bounded contexts are allowed to resolve."""
    container.singleton(IMarketDataSync, _build_market_data_sync)
    container.singleton(IHistoricalKlines, _build_historical_klines)
    container.singleton(IMarketStream, _build_market_stream)
    container.singleton(ISymbolCatalog, _build_symbol_catalog)
    container.singleton(IRangeCoverage, _build_range_coverage)


def _build_market_data_sync(container: IContainer) -> IMarketDataSync:
    """A named factory rather than a lambda, matching `adapter_bindings.py`:
    the `resolve()` must happen when something first asks for the port, never
    during `register()` — `shell/registering_container.py` raises if a module
    resolves while registering, and `ICommandDispatcher` is itself bound by
    another part of the boot."""
    return MarketDataSyncService(container.resolve(ICommandDispatcher))


def _build_historical_klines(container: IContainer) -> IHistoricalKlines:
    """The reader itself, per HLD §3.4: "a port implementation may be the
    existing handler" — no pass-through object and no extra file, which is
    the accidental complexity ADR D2 exists to avoid.

    **This is now the only registration of that class.** When PR 1.1a
    published the port, `query_bindings.py` still bound the same class
    against `GetHistoricalKlinesQuery` for the module's own dispatches — and
    once all six consumers had moved onto the port, nothing in `src/`
    dispatched that query at all. The cleanup after 1.1a's review deleted the
    query, the binding and the `execute()` they reached, so the lifetime
    question those two registrations raised is gone with them: one class, one
    `singleton`, stateless but for the repository it reads.
    """
    return StoredKlinesReader(container.resolve(IMarketDataRepository))


def _build_market_stream(container: IContainer) -> IMarketStream:
    """Dispatches the module's two stream commands, for the reason
    `market_stream_service.py` records: the module's own CLI dispatches them
    too, and a port that reached past them to `ILiveStreamService` would give
    the CLI and the screens two paths to one websocket.

    A named factory rather than a lambda, and late-resolving, for the same
    reason as `_build_market_data_sync` above: `ICommandDispatcher` is bound
    by another part of the boot, and resolving during `register()` is what
    `shell/registering_container.py` refuses.
    """
    return MarketStreamService(container.resolve(ICommandDispatcher))


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
    """The service itself, reading the same repository `IHistoricalKlines`
    reads — no command in the middle, so nothing to dispatch (the same shape
    as `_build_symbol_catalog` above, and unlike the sync and the stream).
    """
    return RangeCoverageService(container.resolve(IMarketDataRepository))
