"""This module's own long-lived state: each venue's trading session
(`VenueSessionStates`, `EPIC-028B`), the lookup every venue-addressed handler
resolves its venue through, and the scheduled services that keep open
positions' mark price and unrealized PnL from going stale between
account-update events.

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
from Sagittarius_Elite_Warrior.src.modules.trading.application.holdings_refresh_service import (
    HoldingsRefreshService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.position_refresh_service import (
    PositionRefreshService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_session_states import (
    VenueSessionStates,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScopes,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.interfaces.i_container import IContainer


def _primary_session_state(container: IContainer) -> TradingSessionState:
    """The primary venue's own state — the venue the single Trading screen
    and Dev Board trade on (`EPIC-028B`). `EPIC-028C` runs one refresh
    service per enabled venue instead."""
    return container.resolve(VenueSessionStates).session_state(
        container.resolve(TradingVenue)
    )


def bind_state(container: IContainer) -> None:
    # `EPIC-028B`: each venue's session state, and the one lookup every
    # venue-addressed handler resolves its venue through.
    container.singleton(VenueSessionStates, VenueSessionStates())
    container.singleton(
        VenueTradingScopes,
        lambda c: VenueTradingScopes(
            c.resolve(IVenueContexts), c.resolve(VenueSessionStates)
        ),
    )

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
            _primary_session_state(c),
            c.resolve(TradingVenue),
        ),
    )

    # `EPIC-027O` — the Holdings table's own equivalent of the refresh above.
    # `TradingModule.boot()` only schedules this one on a Spot venue (its own
    # docstring says why); bound here unconditionally regardless, the same
    # "always bind, only conditionally schedule" split `PositionRefreshService`
    # already uses.
    container.singleton(
        HoldingsRefreshService,
        lambda c: HoldingsRefreshService(
            c.resolve(ICommandDispatcher),
            c.resolve(IEventPublisher),
            _primary_session_state(c),
            c.resolve(TradingVenue),
        ),
    )
