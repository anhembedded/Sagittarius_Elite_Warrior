"""`trading`'s **published** ports: what another context may depend on.

The only binding table this module has, and the reason is the same one
`module.py` records: PR 1.3a moved the code in but left the adapter and
handler registrations in `binance_bot_module.py`. PR 1.3c-4 has since split
the shared `ExchangeSessionFactory` one factory per context, so what kept
those registrations out is gone; moving the dozen of them is PR 1.4's, with
the surfaces.

These four are different: not one of them needs an exchange session or a
credential. Three need only `ICommandDispatcher` (a `core/` port) plus, for the
session, the `TradingSessionState` singleton; the fourth hands back the
`EquityCurveRecorder` singleton the module's own user-data stream writes. Every
one is something this module can ask the container for at build time, so the
published surface can be bound here now and the internals follow later — which
is exactly the split that let PR 0.5 publish `IMarketDataSync` while its
adapters still lived elsewhere.

`singleton`, matching `market_data`: a published port is a stateless façade
over a dispatch, so one instance answers every consumer, and a Presenter
holding it for a screen's lifetime holds nothing another screen could corrupt.
`TradingSessionService` is the one that holds a reference — to the
`TradingSessionState` singleton, which is *meant* to be shared and guards
itself with a lock.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account.account_snapshot_service import (
    AccountSnapshotService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.equity_curve_recorder import (
    EquityCurveRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.order_submission_service import (
    OrderSubmissionService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.trading_session_service import (
    TradingSessionService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
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
from sagittarius_engine.interfaces.i_container import IContainer


def _build_order_submission(container: IContainer) -> OrderSubmissionService:
    return OrderSubmissionService(container.resolve(ICommandDispatcher))


def _build_trading_session(container: IContainer) -> TradingSessionService:
    return TradingSessionService(
        container.resolve(ICommandDispatcher),
        container.resolve(TradingSessionState),
    )


def _build_account_snapshot(container: IContainer) -> AccountSnapshotService:
    return AccountSnapshotService(container.resolve(ICommandDispatcher))


def _equity_curve(container: IContainer) -> EquityCurveRecorder:
    """The recorder itself, not a wrapper: `FuturesUserDataStream` writes the
    container's `EquityCurveRecorder` singleton, so anything else would answer
    with a second, empty curve. The port narrows what a consumer can *do* with
    it (read only), which is the whole point — it does not need a second
    object to do that (`EPIC-025` PR 1.3c-3)."""
    return container.resolve(EquityCurveRecorder)


def bind_published_ports(container: IContainer) -> None:
    """Register the ports other bounded contexts are allowed to resolve.

    Every value is a factory, not an instance: `register()` must never call
    `resolve()` (the declaration guard checks it), so the container is asked
    for `ICommandDispatcher`, `TradingSessionState` and `EquityCurveRecorder`
    when the port is first built, by which time every module has registered.
    """
    container.singleton(IOrderSubmission, _build_order_submission)
    container.singleton(ITradingSession, _build_trading_session)
    container.singleton(IAccountSnapshot, _build_account_snapshot)
    container.singleton(IEquityCurve, _equity_curve)
