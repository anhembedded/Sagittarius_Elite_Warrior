"""`trading`'s **published** ports: what another context may depend on.

The only binding table this module has, and the reason is the same one
`module.py` records: PR 1.3a moved the code in but left the adapter and
handler registrations in `binance_bot_module.py`. PR 1.3c-4 has since split
the shared `ExchangeSessionFactory` one factory per context, so what kept
those registrations out is gone; moving the dozen of them is PR 1.4's, with
the surfaces.

These are different: not one of them needs an exchange session or a
credential. Each service needs only `ICommandDispatcher` (a `core/` port),
its venue, and — for the session and the equity curve — that venue's own
state from `VenueSessionStates` (`EPIC-028B`). Every one is something this
module can ask the container for at build time, so the published surface can
be bound here now and the internals follow later — which is exactly the split
that let PR 0.5 publish `IMarketDataSync` while its adapters still lived
elsewhere.

`singleton`, matching `market_data`: a published port is a stateless façade
over a dispatch, so one instance per venue answers every consumer, and a
Presenter holding it for a screen's lifetime holds nothing another screen
could corrupt. `TradingSessionService` is the one that holds a reference — to
its venue's `TradingSessionState`, which is *meant* to be shared and guards
itself with a lock.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_session_states import (
    VenueSessionStates,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.venue_accounts import (
    VenueAccounts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.venue_trading_ports_registry import (
    VenueTradingPortsRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_snapshot import (
    IAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_equity_curve import (
    IEquityCurve,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_submission import (
    IOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    ITradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_accounts import (
    IVenueAccounts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_trading_ports import (
    VenueTradingPorts,
)
from sagittarius_engine.interfaces.i_container import IContainer


def _build_venue_trading_ports(container: IContainer) -> VenueTradingPortsRegistry:
    return VenueTradingPortsRegistry(
        container.resolve(ICommandDispatcher),
        container.resolve(IVenueContexts),
        container.resolve(VenueSessionStates),
    )


def _primary(container: IContainer) -> VenueTradingPorts:
    return container.resolve(IVenueTradingPorts).primary()


def bind_published_ports(container: IContainer) -> None:
    """Register the ports other bounded contexts are allowed to resolve.

    Every value is a factory, not an instance: `register()` must never call
    `resolve()` (the declaration guard checks it), so the container is asked
    for `ICommandDispatcher` and the venue registries when a port is first
    built, by which time every module has registered.

    `EPIC-028B` — `IVenueTradingPorts` is the per-venue surface. The four
    single ports below are the **primary** venue's own bundle: the venue
    the single Trading screen and Dev Board trade on until `EPIC-028K`/
    `028L` give each venue its own desk, and `EPIC-028M` retires them.
    """
    container.singleton(VenueTradingPortsRegistry, _build_venue_trading_ports)
    container.singleton(
        IVenueTradingPorts, lambda c: c.resolve(VenueTradingPortsRegistry)
    )
    # `EPIC-034D`: the Connect step's read-only accounts, one reader per source.
    container.singleton(
        IVenueAccounts, lambda c: VenueAccounts(c.resolve(IVenueContexts))
    )
    container.singleton(IOrderSubmission, lambda c: _primary(c).order_submission)
    container.singleton(ITradingSession, lambda c: _primary(c).trading_session)
    container.singleton(IAccountSnapshot, lambda c: _primary(c).account_snapshot)
    container.singleton(IEquityCurve, lambda c: _primary(c).equity_curve)
