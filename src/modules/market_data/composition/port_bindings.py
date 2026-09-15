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
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.get_historical_klines import (
    GetHistoricalKlinesQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.sync.market_data_sync_service import (
    MarketDataSyncService,
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
from sagittarius_engine.interfaces.i_container import IContainer


def bind_published_ports(container: IContainer) -> None:
    """Register the ports other bounded contexts are allowed to resolve."""
    container.singleton(IMarketDataSync, _build_market_data_sync)
    container.singleton(IHistoricalKlines, _build_historical_klines)


def _build_market_data_sync(container: IContainer) -> IMarketDataSync:
    """A named factory rather than a lambda, matching `adapter_bindings.py`:
    the `resolve()` must happen when something first asks for the port, never
    during `register()` — `shell/registering_container.py` raises if a module
    resolves while registering, and `ICommandDispatcher` is itself bound by
    another part of the boot."""
    return MarketDataSyncService(container.resolve(ICommandDispatcher))


def _build_historical_klines(container: IContainer) -> IHistoricalKlines:
    """The query handler itself, per HLD §3.4: "a port implementation may be
    the existing handler" — no pass-through object and no extra file, which is
    the accidental complexity ADR D2 exists to avoid.

    It is constructed here rather than resolved, and the difference matters.
    `query_bindings.py` registers the same class against
    `GetHistoricalKlinesQuery` for the module's own dispatches, and that
    binding is transient — one handler per dispatch. A published port is a
    `singleton`, so resolving the query binding here would tie the port's
    lifetime to whatever the dispatcher happened to hand back. Two
    registrations, one class, each with the lifetime its own caller needs;
    the handler is stateless, so nothing is shared but the repository.
    """
    return GetHistoricalKlinesQueryHandler(container.resolve(IMarketDataRepository))
