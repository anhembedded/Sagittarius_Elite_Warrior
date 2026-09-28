"""`EPIC-027O` — keeps the Holdings table from going stale between the
Spot user-data stream's own account events.

@details Mirrors `PositionRefreshService`'s shape (re-fetch, republish
through the existing event pipe, no-op while trading is disabled) but
publishes one `HoldingsChangedEvent` carrying the whole set — see that
event's own docstring for why this never needs a changed/closed pair the
way positions do. `TradingModule.boot()` only schedules this service's
`refresh_once()` on a Spot venue (its own docstring explains why: a
Futures venue always answers `None` here, so polling it would be a wasted
network round trip on every tick).
"""

from __future__ import annotations

import logging
from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_holdings import (
    GetHoldingsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.holdings_changed_event import (
    HoldingsChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)

logger = logging.getLogger("App.HoldingsRefresh")


class HoldingsRefreshService:
    """@brief Re-fetches Spot holdings from the exchange and republishes
    them through `HoldingsChangedEvent`.

    @details `refresh_once()` is a no-op while trading is disabled, same
    as `PositionRefreshService` — safe to call on a fixed interval forever
    once scheduled.
    """

    def __init__(
        self,
        dispatcher: ICommandDispatcher,
        event_publisher: IEventPublisher,
        session_state: TradingSessionState,
    ) -> None:
        self._dispatcher = dispatcher
        self._event_publisher = event_publisher
        self._session_state = session_state

    def refresh_once(self) -> None:
        if not self._session_state.enabled:
            return

        try:
            holdings = cast(
                tuple[SpotHolding, ...],
                self._dispatcher.dispatch(GetHoldingsQuery, GetHoldingsQuery()),
            )
        except Exception as exc:  # noqa: BLE001 - worker boundary: a transient network hiccup must not kill the scheduler's job thread, and there is nothing user-facing to report for one missed tick — the next one simply tries again
            logger.debug("Holdings refresh failed: %s", exc)
            return

        self._event_publisher.publish(HoldingsChangedEvent(holdings=holdings))
