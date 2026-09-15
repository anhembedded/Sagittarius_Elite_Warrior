"""`BUG-117` — keeps every open position's mark price/unrealized PnL from
going stale between exchange-driven `ACCOUNT_UPDATE` events.

@details `FuturesUserDataStream._handle_account_update()` only recomputes a
position's `LivePosition` when the exchange pushes an `ACCOUNT_UPDATE` — a
fill, a funding settlement. Nothing else ever refreshed it, so an open
position sat at whatever mark price its last fill left it at while the live
chart right next to it kept ticking (reported directly: Binance showed
+15.98 USDT unrealized, the app showed +2.57 USDT, frozen since the last
fill).

One instance, one poll, regardless of how many screens display positions —
`OrderFeed`/`EquityFeed`/`HealthCheckCoordinator` all exist for the exact
same reason (`architecture-rule.md` §6: one place hears an event, many
screens display it). This service re-publishes through the same
`PositionChangedEvent`/`PositionClosedEvent` every screen already listens
to via `OrderFeed` — no new UI wiring needed on this screen or the next one.

`refresh_once()` does not compute any `LivePosition` field itself — every
value it publishes came straight off `GetOpenPositionsQuery`'s own,
already-tested wire-parsing pipeline (`LivePosition`'s own docstring: "this
app never computes any of its fields, only parses them off the wire").
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
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_open_positions import (
    GetOpenPositionsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.position_changed_event import (
    PositionChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.position_closed_event import (
    PositionClosedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.live_position import (
    LivePosition,
)

logger = logging.getLogger("App.PositionRefresh")


class PositionRefreshService:
    """@brief Re-fetches open positions from the exchange and republishes
    them through the existing `PositionChangedEvent`/`PositionClosedEvent`
    pipe.

    @details `refresh_once()` is a no-op while trading is disabled — safe
    to call on a fixed interval forever, from the moment the app boots,
    regardless of session state. Whoever schedules the interval (`boot()`
    registers it once with the engine's own `Scheduler`) does not need to
    start or stop it in step with Enable/Disable Trading; this service
    reads `TradingSessionState.enabled` itself, once per tick.
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
        self._known_symbols: set[str] = set()

    def refresh_once(self) -> None:
        if not self._session_state.enabled:
            return

        try:
            # `ICommandDispatcher.dispatch()`'s own signature returns
            # `object` — `cast` documents the trust explicitly rather than
            # annotating past it, same idiom `LiveTradingCoordinator` uses
            # for its own `ExecuteOrderCommand` dispatch.
            positions = cast(
                tuple[LivePosition, ...],
                self._dispatcher.dispatch(
                    GetOpenPositionsQuery, GetOpenPositionsQuery()
                ),
            )
        except Exception as exc:  # noqa: BLE001 - worker boundary: a transient network hiccup must not kill the scheduler's job thread, and there is nothing user-facing to report for one missed tick — the next one simply tries again
            logger.debug("Position refresh failed: %s", exc)
            return

        current_symbols = {position.symbol for position in positions}
        for position in positions:
            self._event_publisher.publish(PositionChangedEvent(position=position))
        for symbol in self._known_symbols - current_symbols:
            self._event_publisher.publish(PositionClosedEvent(symbol=symbol))
        self._known_symbols = current_symbols
