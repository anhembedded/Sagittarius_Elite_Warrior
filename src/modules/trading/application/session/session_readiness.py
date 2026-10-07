"""`EPIC-034C` — `SessionReadiness`: the one place a venue's order session is
opened, and so the one place the account is reconciled before any order.

@details This is the reconciliation `EnsureSessionReadyCommandHandler` ran when
the user switched trading on (`EPIC-021G` §2.4), moved here unchanged and
called by the three actions that start trading — starting a bot, arming a
strategy and placing a manual order (decision D3 of `EPIC-034`) — instead of
by a switch. `TradingSessionState.enable()` is called from here and from
nowhere else (`test_every_order_is_reconciled.py`).

Reads the whole account every time the session is closed, never trusts a
previous session's state: `get_positions()`/`get_open_orders()` with no symbol
read the *whole* account. Any existing position refuses outright — this app
never auto-adopts or auto-closes a position it did not open itself.

**Open stays open.** Once the session is open a second call answers `ready`
with nothing read (`already_open`): reconciling again would refuse on the
positions this app opened itself, and `enable()` would clear every bot's
budget. Only Emergency Stop closes it, and nothing reopens it but the next
deliberate action: an automated caller (a bot's tick, a strategy's signal) never
calls this, so a late order cannot undo the stop.

`BUG-088` — the generation is read *before* the two network round-trips, so a
concurrent Emergency Stop that lands meanwhile makes this lose
(`SUPERSEDED_BY_CONCURRENT_STATE_CHANGE`). Calls for one venue are serialised,
so two actions starting together reconcile once, not twice.

`EPIC-027M` — on a Spot venue `positions` is always empty (holding assets is
normal there), so what Spot records instead is the account's per-asset
holdings, the baseline Emergency Stop later sells above.

Publishes `TradingSwitchChangedEvent(ENABLED)` once the session has opened (the
event's name predates `EPIC-034C`: "the venue's trading turned on"). A refused
or superseded call changed nothing and publishes nothing.
"""

from __future__ import annotations

import logging
import threading

from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScopes,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
    TradingSwitchChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_ready_result import (
    SessionBlockReason,
    SessionReadyResult,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.TradingSession")


class SessionReadiness:
    """@brief Opens a venue's order session after reconciling its account."""

    def __init__(self, scopes: VenueTradingScopes, publisher: IEventPublisher) -> None:
        self._scopes = scopes
        self._publisher = publisher
        self._venue_locks: dict[TradingVenue, threading.Lock] = {}

    def ensure_ready(self, venue: TradingVenue) -> SessionReadyResult:
        """@brief `venue`'s order session is open when this answers `ready`.

        Network round trips on a closed session: call it from a worker thread.
        """
        if not venue.supports_order_submission:
            return self._blocked(SessionBlockReason.TRADING_VENUE_DISABLED)
        with self._venue_locks.setdefault(venue, threading.Lock()):
            return self._ensure_ready_serialised(venue)

    def _ensure_ready_serialised(self, venue: TradingVenue) -> SessionReadyResult:
        # `EPIC-028B` — everything below is `venue`'s own: its state,
        # connection, client and user data stream. Opening one venue's session
        # never touches the other's.
        scope = self._scopes.get(venue)
        session_state = scope.session_state
        if session_state.stop_in_progress:
            return self._blocked(SessionBlockReason.EMERGENCY_STOP_IN_PROGRESS)
        if session_state.enabled:
            return SessionReadyResult(
                ready=True,
                block_reason=None,
                reconciled_positions=(),
                reconciled_open_orders=(),
                already_open=True,
            )

        # `BUG-088` — read *before* the two network round-trips below, not
        # after: `enable()` only applies if nothing else (a concurrent
        # Emergency Stop, most importantly) mutated `_session_state` while
        # this reconciliation was in flight.
        generation_before_reconciliation = session_state.generation

        status = scope.ports.account_reader.check_connection()
        if not status.reachable or status.failure is not None:
            return self._blocked(SessionBlockReason.CONNECTION_NOT_READY)

        trading_client = scope.ports.client_factory.create(
            OrderSubmissionMode.VALIDATE_ONLY
        )
        positions = tuple(trading_client.get_positions())
        open_orders = tuple(trading_client.get_open_orders())
        if positions:
            return SessionReadyResult(
                ready=False,
                block_reason=SessionBlockReason.UNEXPECTED_POSITIONS,
                reconciled_positions=positions,
                reconciled_open_orders=open_orders,
            )

        spot_baseline_holdings = (
            {holding.asset: holding.total for holding in status.holdings}
            if venue.market_type is MarketType.SPOT and status.holdings is not None
            else None
        )
        # `positions` is provably empty here (the `if positions:` branch above
        # already returned otherwise) — `set()`, not a set built from it.
        applied = session_state.enable(
            set(),
            expected_generation=generation_before_reconciliation,
            spot_baseline_holdings=spot_baseline_holdings,
        )
        if not applied:
            logger.warning(
                "Session on %s not opened — its state changed while reconciling "
                "(e.g. a concurrent Emergency Stop).",
                venue.value,
            )
            return SessionReadyResult(
                ready=False,
                block_reason=(SessionBlockReason.SUPERSEDED_BY_CONCURRENT_STATE_CHANGE),
                reconciled_positions=positions,
                reconciled_open_orders=open_orders,
            )

        scope.ports.user_data_stream.start()
        self._publisher.publish(
            TradingSwitchChangedEvent(True, TradingSwitchCause.ENABLED, venue=venue)
        )
        if spot_baseline_holdings is not None:
            logger.info(
                "Spot holdings baseline recorded for this session: %d asset(s).",
                len(spot_baseline_holdings),
            )
        logger.info(
            "Order session opened on %s (%d open orders reconciled).",
            venue.value,
            len(open_orders),
        )
        return SessionReadyResult(
            ready=True,
            block_reason=None,
            reconciled_positions=positions,
            reconciled_open_orders=open_orders,
        )

    @staticmethod
    def _blocked(reason: SessionBlockReason) -> SessionReadyResult:
        return SessionReadyResult(
            ready=False,
            block_reason=reason,
            reconciled_positions=(),
            reconciled_open_orders=(),
        )
