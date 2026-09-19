"""This module's own long-lived state: the one live trading session, and the
scheduled service that keeps its open positions' mark price and unrealized
PnL from going stale between account-update events.

`EPIC-025E` PR 4.4f-4 — moved out of `binance_bot_module.py` alongside
`adapter_bindings.py`'s own move, same shape `strategy/composition/
state_bindings.py` used at PR 4.4f-2: nothing here changes *what* gets
built, only *where* the binding that builds it lives. `PositionRefreshService`
is bound here, not `adapter_bindings.py`, because it depends on
`TradingSessionState` — the same-file dependency the two share is the reason
they are one file rather than two (`architecture-rule.md` §5 rule 5).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.position_refresh_service import (
    PositionRefreshService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from sagittarius_engine.interfaces.i_container import IContainer


def bind_state(container: IContainer) -> None:
    # EPIC-021G: one per app process — never persisted, never seeded from
    # config on boot (see the class's own docstring for why).
    container.singleton(TradingSessionState, TradingSessionState)

    # `BUG-117` — keeps every open position's mark price/unrealized PnL from
    # going stale between `ACCOUNT_UPDATE` events (a fill, a funding
    # settlement); nothing else ever refreshed it. One instance, scheduled
    # once at boot (`TradingModule.boot()`) via the engine's own `Scheduler`,
    # not one per screen — it reads `TradingSessionState.enabled` itself
    # every tick, so no Enable/Disable/Emergency-Stop handler needs to start
    # or stop it.
    container.singleton(
        PositionRefreshService,
        lambda c: PositionRefreshService(
            c.resolve(ICommandDispatcher),
            c.resolve(IEventPublisher),
            c.resolve(TradingSessionState),
        ),
    )
