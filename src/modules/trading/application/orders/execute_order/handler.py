"""`EPIC-021G` — `ExecuteOrderCommandHandler`: the one place in this app
allowed to construct `FuturesTradingClient` with `OrderSubmissionMode.LIVE`.
Guarded by `tests/unit/infrastructure/binance/
test_order_submission_mode_live_is_restricted.py`, which allowlists this
exact file — nowhere else."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client import (
    FuturesTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.command import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order.handler import (
    PreviewOrderQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderNotionalRejection,
    ExecuteOrderResult,
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    NotionalCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.trading_limit_policy import (
    TradingLimitContext,
    TradingLimitPolicy,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_trading_session_factory import (
    ITradingSessionFactory,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.CommandHandler")


class ExecuteOrderCommandHandler(
    ICommandHandler[ExecuteOrderCommand, ExecuteOrderResult]
):
    def __init__(
        self,
        trading_venue: TradingVenue,
        session_state: TradingSessionState,
        account_reader: ITradingAccountReader,
        preview_handler: PreviewOrderQueryHandler,
        limits_policy: TradingLimitPolicy,
        session_factory: ITradingSessionFactory,
        credentials_provider: IExchangeCredentialsProvider,
        metadata_provider: IMarketMetadataProvider,
    ) -> None:
        self._trading_venue = trading_venue
        self._session_state = session_state
        self._account_reader = account_reader
        self._preview_handler = preview_handler
        self._limits_policy = limits_policy
        self._session_factory = session_factory
        self._credentials_provider = credentials_provider
        self._metadata_provider = metadata_provider

    def execute(self, command: ExecuteOrderCommand) -> ExecuteOrderResult:
        logger.debug(
            "Handling ExecuteOrderCommand for %s (live=%s)",
            command.order_request.symbol,
            command.live,
        )

        gate = self._first_blocked_safety_gate(command)
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

        symbol = command.order_request.symbol
        # `EPIC-024B` — held for the whole evaluate→submit→record sequence,
        # network call included, not just the state mutations: a second
        # real caller of this command now exists (a human, via the manual
        # trading form, alongside the strategy's own tick), so two
        # dispatches reading `orders_sent_this_session` before either one's
        # order lands is a real race, not a hypothetical one. See
        # `TradingSessionState.live_submission_guard()`'s own docstring.
        with self._session_state.live_submission_guard():
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
            holder = self._session_state.lease_holder(symbol)
            if holder is not None and holder != command.owner_id:
                return ExecuteOrderResult(
                    ExecuteOrderSafetyGate.SYMBOL_LEASED, preview, (), None
                )

            now = datetime.now(UTC)
            context = TradingLimitContext(
                orders_sent_this_session=self._session_state.orders_sent_this_session,
                order_notional=preview.estimated_notional,
                open_position_count_for_symbol=self._session_state.open_position_count(
                    symbol
                ),
                time_since_last_order_for_symbol=self._session_state.time_since_last_order(
                    symbol, now
                ),
            )
            checks = self._limits_policy.evaluate(context)
            violation = next((c.violation for c in checks if not c.passed), None)
            if violation is not None:
                return ExecuteOrderResult(violation, preview, checks, None, context)

            if not command.live:
                return ExecuteOrderResult(None, preview, checks, None, context)

            trading_client = FuturesTradingClient(
                self._session_factory,
                self._credentials_provider,
                self._metadata_provider,
                OrderSubmissionMode.LIVE,
            )
            submitted_order = trading_client.place_order(preview.order)
            self._session_state.record_order_sent(symbol, now)
            logger.info(
                "Live order submitted: %s %s", symbol, submitted_order.client_order_id
            )
            return ExecuteOrderResult(None, preview, checks, submitted_order, context)

    def _first_blocked_safety_gate(
        self, command: ExecuteOrderCommand
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
        if self._trading_venue is not TradingVenue.FUTURES_TESTNET:
            return ExecuteOrderSafetyGate.TRADING_VENUE_DISABLED
        if not self._session_state.enabled:
            return ExecuteOrderSafetyGate.TRADING_SWITCH_OFF
        holder = self._session_state.lease_holder(command.order_request.symbol)
        if holder is not None and holder != command.owner_id:
            return ExecuteOrderSafetyGate.SYMBOL_LEASED
        status = self._account_reader.check_connection()
        if not status.reachable or status.failure is not None:
            return ExecuteOrderSafetyGate.CONNECTION_NOT_READY
        return None
