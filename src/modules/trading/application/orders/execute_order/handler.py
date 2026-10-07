"""`EPIC-021G` — `ExecuteOrderCommandHandler`: the one place in this app
allowed to reference `OrderSubmissionMode.LIVE`. Guarded by
`tests/unit/architecture/test_order_submission_mode_live_is_restricted.py`,
which allowlists this exact file — nowhere else.

`EPIC-027F` — resolves its trading client from `ITradingClientFactory`
rather than constructing `FuturesTradingClient` itself (see that port's own
docstring)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.command import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order.handler import (
    PreviewOrderQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.session_readiness import (
    SessionReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScope,
    VenueTradingScopes,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderNotionalRejection,
    ExecuteOrderPriceRejection,
    ExecuteOrderResult,
    ExecuteOrderSafetyGate,
    ExecuteOrderStopRejection,
    ExecuteOrderTypeRejection,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    NotionalCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.price_band_check import (
    PriceBandCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.stop_price_check import (
    StopPriceCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    TradingLimitContext,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.trading_limit_policy import (
    TradingLimitPolicy,
)

logger = logging.getLogger("App.CommandHandler")


class ExecuteOrderCommandHandler(
    ICommandHandler[ExecuteOrderCommand, ExecuteOrderResult]
):
    """@details `EPIC-028B` — acts on `command.venue` only: its session
    state, its connection and its client come from one
    `VenueTradingScopes.get()` call, so an order can never be checked
    against one venue and sent to another.

    `EPIC-034C` — every live order needs the venue's order session open
    (`TRADING_SWITCH_OFF` otherwise), and the session opens only through
    `SessionReadiness`, which reconciles the account first. A manual order opens
    it here; Start bot and arm strategy open it in their own use cases."""

    def __init__(
        self,
        scopes: VenueTradingScopes,
        preview_handler: PreviewOrderQueryHandler,
        limits_policy: TradingLimitPolicy,
        readiness: SessionReadiness,
    ) -> None:
        self._scopes = scopes
        self._preview_handler = preview_handler
        self._limits_policy = limits_policy
        self._readiness = readiness

    def execute(self, command: ExecuteOrderCommand) -> ExecuteOrderResult:
        logger.debug(
            "Handling ExecuteOrderCommand for %s on %s (live=%s)",
            command.order_request.symbol,
            command.venue.value,
            command.live,
        )

        # Before any lookup: a venue that cannot trade has nothing to
        # resolve, and refusing it costs nothing.
        if not command.venue.supports_order_submission:
            return ExecuteOrderResult(
                ExecuteOrderSafetyGate.TRADING_VENUE_DISABLED, None, (), None
            )
        scope = self._scopes.get(command.venue)
        session_state = scope.session_state

        # `EPIC-034C` — a manual live order is the deliberate action that
        # opens the order session: the same reconciliation Start bot and arm
        # strategy run, before the order is read or anything is sent. An
        # automated order (`opens_session` False) never reaches it, so it
        # cannot reopen a session Emergency Stop closed.
        if command.live and command.opens_session:
            opened = self._readiness.ensure_ready(command.venue)
            if not opened.ready:
                return ExecuteOrderResult(opened.block_reason, None, (), None)

        gate = self._first_blocked_safety_gate(command, scope)
        if gate is not None:
            return ExecuteOrderResult(gate, None, (), None)

        preview = self._preview_handler.execute(command.order_request)

        # `BUG-090` — refuse before the four session limits, and well
        # before any network call, rather than letting an order this
        # app's own normalization already knows is too small round-trip
        # to the exchange for a `-4164` rejection.
        if preview.notional_check is NotionalCheck.INSUFFICIENT:
            return ExecuteOrderResult(
                ExecuteOrderNotionalRejection.MIN_NOTIONAL, preview, (), None
            )
        # `EPIC-028O` — the same before-the-network refusals: first a stop
        # that would trigger at once (wrong on any venue), then an order type
        # this venue's client cannot send. Named answers on the dry run and
        # the live path alike, never an exception from inside `place_order`.
        if preview.stop_check is StopPriceCheck.WRONG_SIDE:
            return ExecuteOrderResult(
                ExecuteOrderStopRejection.STOP_ON_WRONG_SIDE, preview, (), None
            )
        # `BUG-147` — a price outside the venue's band, refused by name
        # instead of the exchange's `-1013 PERCENT_PRICE_BY_SIDE`.
        if preview.price_band_check is PriceBandCheck.OUTSIDE:
            return ExecuteOrderResult(
                ExecuteOrderPriceRejection.OUTSIDE_PRICE_BAND, preview, (), None
            )
        accepted = scope.ports.client_factory.accepted_order_types()
        if preview.order.order_type not in accepted:
            return ExecuteOrderResult(
                ExecuteOrderTypeRejection.NOT_SENDABLE_ON_VENUE, preview, (), None
            )

        symbol = command.order_request.symbol
        # `EPIC-024B` — held for the whole evaluate→submit→record sequence,
        # network call included, not just the state mutations: a second
        # real caller of this command now exists (a human, via the manual
        # trading form, alongside the strategy's own tick), so two
        # dispatches reading `orders_sent_this_session` before either one's
        # order lands is a real race, not a hypothetical one. See
        # `TradingSessionState.live_submission_guard()`'s own docstring.
        with session_state.live_submission_guard():
            # `EPIC-025` PR 2.1f — the symbol lease, and it is inside this lock
            # for the reason `Docs/SDD/05` §3 calls claim-then-execute: reading
            # the holder before acquiring the guard would let a strategy arm in
            # the gap between the check and the order, which is exactly the
            # race the check exists to prevent.
            #
            # It refuses an order from anyone the symbol was not leased to. The
            # rule itself is the user's decision of 2026-09-09 (`PRO-003`
            # §4.1.2): manually trading the symbol an armed strategy is
            # watching makes that strategy lose track of its real position,
            # *even while it is currently flat*, because
            # `order_intent_for()` never re-reads the position and assumes it
            # started flat. What moved here is the enforcement — it used to sit
            # in `DashboardPresenter._run_manual_order()`, so the CLI and any
            # future order path were not covered by a rule the user had asked
            # for.
            holder = session_state.lease_holder(symbol)
            if holder is not None and holder != command.owner_id:
                return ExecuteOrderResult(
                    ExecuteOrderSafetyGate.SYMBOL_LEASED, preview, (), None
                )

            now = datetime.now(UTC)
            # `EPIC-029` ADR D6 — a tagged order is judged by its owner's
            # budget and book, read inside this lock like everything else.
            tag = command.order_request.client_order_tag
            context = TradingLimitContext(
                orders_sent_this_session=session_state.orders_sent_this_session,
                order_notional=preview.estimated_notional,
                open_position_count_for_symbol=session_state.open_position_count(
                    symbol
                ),
                time_since_last_order_for_symbol=session_state.time_since_last_order(
                    symbol, now
                ),
                purpose=command.purpose,
                client_order_tag=tag,
                owner_budget=(
                    None
                    if tag is None
                    else session_state.owner_books.facts(
                        tag, command.owner_id, preview.order, now
                    )
                ),
            )
            checks = self._limits_policy.evaluate(context)
            violation = next((c.violation for c in checks if not c.passed), None)
            limits = self._limits_policy.limits
            if violation is not None:
                return ExecuteOrderResult(
                    violation, preview, checks, None, context, limits
                )

            if not command.live:
                return ExecuteOrderResult(None, preview, checks, None, context, limits)

            trading_client = scope.ports.client_factory.create(OrderSubmissionMode.LIVE)
            # `EPIC-029` ADR D6 — a budgeted owner's order goes to its book,
            # not to the signal limits' bookkeeping: it neither marks the
            # symbol open nor delays another owner's next order. It is
            # recorded **before** the send, so a send that raises still
            # counts in the spacing and the rate, and the order, whose outcome
            # is then unknown, stays open until a fill or an end settles it,
            # or the session ends (the `EPIC-029A` review). The price: an
            # order the venue refused outright holds its open slot and its
            # quote until then, which can only stop the bot, never overspend.
            if tag is not None:
                session_state.owner_books.record_sent(
                    tag, preview.order, preview.estimated_notional, now
                )
            submitted_order = trading_client.place_order(preview.order)
            # `EPIC-028I` — a protective order or a close is not a new trade:
            # it neither uses up the session's orders nor delays the next entry.
            if tag is None and not command.purpose.only_reduces:
                session_state.record_order_sent(
                    symbol, now, venue_has_positions=command.venue.has_positions
                )
            logger.info(
                "Live order submitted on %s: %s %s",
                command.venue.value,
                symbol,
                submitted_order.client_order_id,
            )
            return ExecuteOrderResult(
                None, preview, checks, submitted_order, context, limits
            )

    @staticmethod
    def _first_blocked_safety_gate(
        command: ExecuteOrderCommand, scope: VenueTradingScope
    ) -> ExecuteOrderSafetyGate | None:
        """@details Ordered by cost, cheapest first, and the lease sits ahead of
        the connection check deliberately (`EPIC-025` PR 2.1f). The refusal it
        replaces — `DashboardPresenter`'s own hard block — was explicitly free:
        *"No network call needed for this check, so it runs before reading the
        open positions — a blocked attempt costs nothing."* Behind
        `check_connection()` it would have cost a round trip, and a user with a
        flaky connection would have been told `CONNECTION_NOT_READY` about an
        order that was never going to be allowed anyway.

        This read is **not** the authoritative one: it is outside
        `live_submission_guard()`, so a strategy could still arm between here
        and the submission. `execute()` reads the holder again inside that lock,
        which is the check that closes the race. Two reads, one cheap and one
        atomic, is the whole reason this method can stay free.
        """
        if not scope.session_state.enabled:
            return ExecuteOrderSafetyGate.TRADING_SWITCH_OFF
        holder = scope.session_state.lease_holder(command.order_request.symbol)
        if holder is not None and holder != command.owner_id:
            return ExecuteOrderSafetyGate.SYMBOL_LEASED
        status = scope.ports.account_reader.check_connection()
        if not status.reachable or status.failure is not None:
            return ExecuteOrderSafetyGate.CONNECTION_NOT_READY
        return None
