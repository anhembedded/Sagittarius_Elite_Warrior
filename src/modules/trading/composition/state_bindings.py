"""This module's own long-lived state: each venue's trading session
(`VenueSessionStates`, `EPIC-028B`) and the lookup every venue-addressed
handler resolves its venue through. The scheduled refresh services that used
to be bound here are built per venue at boot since `EPIC-028C`
(`venue_refresh_services.py`).

`EPIC-025E` PR 4.4f-4 — moved out of `binance_bot_module.py` alongside
`adapter_bindings.py`'s own move, same shape `strategy/composition/
state_bindings.py` used at PR 4.4f-2: nothing here changes *what* gets
built, only *where* the binding that builds it lives.
"""

from __future__ import annotations

import time

from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.session_readiness import (
    SessionReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.shared_account_status import (
    SharedAccountStatus,
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
from sagittarius_engine.interfaces.i_container import IContainer


def bind_state(container: IContainer) -> None:
    # `EPIC-028B`: each venue's session state, and the one lookup every
    # venue-addressed handler resolves its venue through.
    container.singleton(VenueSessionStates, VenueSessionStates())
    # `EPIC-035V`: the one account read the holdings and the summary refreshes of
    # a tick share, so a Spot venue is read once per tick, not twice.
    container.singleton(SharedAccountStatus, SharedAccountStatus(time.monotonic))
    container.singleton(
        VenueTradingScopes,
        lambda c: VenueTradingScopes(
            c.resolve(IVenueContexts), c.resolve(VenueSessionStates)
        ),
    )
    # `EPIC-034C`: the one reconciliation, shared by `EnsureSessionReadyCommand`'s
    # handler and the manual order path (`ExecuteOrderCommandHandler`).
    container.singleton(
        SessionReadiness,
        lambda c: SessionReadiness(
            c.resolve(VenueTradingScopes), c.resolve(IEventPublisher)
        ),
    )
