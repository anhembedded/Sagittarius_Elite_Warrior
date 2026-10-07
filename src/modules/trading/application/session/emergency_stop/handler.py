"""`EPIC-021K` §2.2 — `EmergencyStopCommandHandler`: the second file this
app allows to reference `OrderSubmissionMode.LIVE` (see
`ExecuteOrderCommandHandler`'s own docstring for the first, and
`tests/unit/architecture/test_order_submission_mode_live_is_restricted.py`
for the guard listing both by name). `EPIC-027F` — resolves its trading
client from `ITradingClientFactory` rather than constructing
`FuturesTradingClient` itself.

@details Does **not** go through `ExecuteOrderCommand`/`DisableTradingCommand`
for its own steps, on purpose:

- `ExecuteOrderCommandHandler._first_blocked_safety_gate()` refuses
  whenever `not session_state.enabled` — and step 1 here disables trading
  *before* step 3 needs to place closing orders, so routing step 3 through
  `ExecuteOrderCommand` would make it refuse every single time, the exact
  opposite of what an emergency close needs.
- Reusing `DisableTradingCommandHandler`'s logic inline (rather than
  dispatching that command) matches this app's existing pattern of
  handlers taking shared services as direct constructor dependencies
  (`ExecuteOrderCommandHandler` does the same for `TradingSessionState`),
  not calling one handler from another through the dispatcher.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_books import (
    OwnerShare,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop.command import (
    EmergencyStopCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop.liquidation_minimum import (
    min_split_quantity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScope,
    VenueTradingScopes,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    generate_client_order_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.emergency_stop_result import (
    EmergencyStopResult,
    EmergencyStopStepResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
    TradingSwitchChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holdings_close_policy import (
    sellable_spot_quantity,
    split_liquidation,
)

logger = logging.getLogger("App.CommandHandler")

#: Phase 1 supports USDT-quoted pairs only (ADR D9) — the quote asset a
#: Spot asset's trading symbol is built against, matching
#: `SpotAccountReader`'s own convention (`f"{asset}{_QUOTE_ASSET}"`).
_QUOTE_ASSET = "USDT"


class EmergencyStopCommandHandler(
    ICommandHandler[EmergencyStopCommand, EmergencyStopResult]
):
    """
    @brief Handler for `EmergencyStopCommand` — three steps, always
    attempted in this exact order (`EPIC-021K` §2.2):

    1. Disable trading — blocks new orders *first*; reversing this order
       would mean an order could still slip in while orders are being
       cancelled and positions closed.
    2. Cancel every open order, whole-account (`ITradingClient.
       get_open_orders()` takes no symbol; `cancel_all_orders()` is
       per-symbol, so this groups by symbol first).
    3. Close every open position with a `MARKET` `reduce_only` order in
       the opposite direction.

    Never gated on `TradingVenue`/connection readiness — same reasoning
    `DisableTradingCommandHandler` documents for step 1: an emergency stop
    must always be attempted. A step's own API calls failing (network,
    exchange rejection, insufficient margin) is reported through that
    step's own `EmergencyStopStepResult`, not raised — one step failing
    must never prevent the next one from being attempted.

    `EPIC-027M` — step 3 branches by the command venue's `market_type`: Spot has
    no `LivePosition` to close (`ITradingClient.get_positions()` always
    answers `[]` there), so "close" means selling each asset's surplus over
    the session's own baseline (`TradingSessionState.spot_baseline_holdings()`)
    instead. One dispatch point (`_close_all_positions`), not scattered
    venue checks, per `code/quality.md` §3.

    `EPIC-029` ADR D7 — step 1 publishes `TradingSwitchChangedEvent
    (EMERGENCY_STOP)` right after the disable, before any order is read or
    cancelled, so a bot learns of the stop before its cancels reach it. It
    publishes even when trading was already off: the stop cancels and sells
    regardless. A disable that raised publishes nothing.
    """

    def __init__(self, scopes: VenueTradingScopes, publisher: IEventPublisher) -> None:
        self._scopes = scopes
        self._publisher = publisher

    def execute(self, command: EmergencyStopCommand) -> EmergencyStopResult:
        logger.warning("Handling EmergencyStopCommand on %s", command.venue.value)
        # `EPIC-028B` — one venue's stop: its session, orders, positions and
        # Spot baseline. Another venue's session is never read or touched.
        scope = self._scopes.get(command.venue)

        # `EPIC-029` ADR D6 r2 — read before step 1 clears the books: each
        # bot's share of the Spot liquidation goes out under its own tag.
        owner_shares = scope.session_state.owner_books.shares()
        trading_disabled = self._disable_trading(scope)

        trading_client = scope.ports.client_factory.create(OrderSubmissionMode.LIVE)
        orders_cancelled = self._cancel_all_orders(trading_client)
        positions_closed = self._close_all_positions(
            trading_client, scope, owner_shares
        )
        final_positions, final_open_orders, final_state_confirmed = (
            self._read_final_state(trading_client)
        )

        result = EmergencyStopResult(
            trading_disabled,
            orders_cancelled,
            positions_closed,
            final_positions,
            final_open_orders,
            final_state_confirmed,
        )
        if result.fully_succeeded:
            logger.warning(
                "Emergency stop on %s completed: trading disabled, all orders "
                "cancelled, all positions closed.",
                command.venue.value,
            )
        else:
            logger.error(
                "Emergency stop on %s completed with failures: %s",
                command.venue.value,
                result,
            )
        return result

    def _disable_trading(self, scope: VenueTradingScope) -> EmergencyStopStepResult:
        try:
            scope.session_state.disable()
            self._publisher.publish(
                TradingSwitchChangedEvent(
                    False, TradingSwitchCause.EMERGENCY_STOP, venue=scope.venue
                )
            )
            scope.ports.user_data_stream.stop()
            return EmergencyStopStepResult(True, "Trading disabled.")
        except Exception as exc:  # noqa: BLE001 - report every failure, never let one abort the remaining steps
            return EmergencyStopStepResult(False, f"Error disabling trading: {exc}")

    def _cancel_all_orders(
        self, trading_client: ITradingClient
    ) -> EmergencyStopStepResult:
        try:
            open_orders = trading_client.get_open_orders()
        except Exception as exc:  # noqa: BLE001
            return EmergencyStopStepResult(False, f"Error reading open orders: {exc}")
        if not open_orders:
            return EmergencyStopStepResult(True, "No open orders.")

        symbols = sorted({order.symbol for order in open_orders})
        cancelled_count = 0
        for symbol in symbols:
            try:
                cancelled_count += len(trading_client.cancel_all_orders(symbol))
            except Exception as exc:  # noqa: BLE001
                remaining = len(open_orders) - cancelled_count
                return EmergencyStopStepResult(
                    False,
                    f"Cancelled {cancelled_count}/{len(open_orders)} open orders — "
                    f"error on {symbol}: {exc}. {remaining} orders still not cancelled.",
                )
        return EmergencyStopStepResult(
            True, f"Cancelled {cancelled_count} open orders."
        )

    def _close_all_positions(
        self,
        trading_client: ITradingClient,
        scope: VenueTradingScope,
        owner_shares: tuple[OwnerShare, ...],
    ) -> EmergencyStopStepResult:
        """@brief Dispatches step 3 by venue market type — the one place
        this handler branches on it (`code/quality.md` §3), rather than a
        Futures/Spot check scattered across the step's own body."""
        if scope.venue.market_type is MarketType.SPOT:
            return self._sell_spot_surplus_holdings(trading_client, scope, owner_shares)
        return self._close_all_futures_positions(trading_client)

    def _close_all_futures_positions(
        self, trading_client: ITradingClient
    ) -> EmergencyStopStepResult:
        try:
            positions = trading_client.get_positions()
        except Exception as exc:  # noqa: BLE001
            return EmergencyStopStepResult(False, f"Error reading positions: {exc}")
        if not positions:
            return EmergencyStopStepResult(True, "No open positions.")

        closed_count = 0
        for position in positions:
            closing_side = (
                OrderSide.SELL if position.side is PositionSide.LONG else OrderSide.BUY
            )
            closing_order = Order(
                client_order_id=generate_client_order_id(),
                symbol=position.symbol,
                side=closing_side,
                order_type=OrderType.MARKET,
                quantity=abs(position.position_amt),
                reduce_only=True,
            )
            try:
                trading_client.place_order(closing_order)
                closed_count += 1
            except Exception as exc:  # noqa: BLE001
                remaining = len(positions) - closed_count
                return EmergencyStopStepResult(
                    False,
                    f"Closed {closed_count}/{len(positions)} positions — error on "
                    f"{position.symbol}: {exc}. {remaining} positions still open.",
                )
        return EmergencyStopStepResult(True, f"Closed {closed_count} positions.")

    @staticmethod
    def _sell_spot_surplus_holdings(
        trading_client: ITradingClient,
        scope: VenueTradingScope,
        owner_shares: tuple[OwnerShare, ...],
    ) -> EmergencyStopStepResult:
        """@brief Sells each Spot asset's surplus over the session's own
        baseline (`EPIC-027M` AC1-AC3) — never the baseline itself, and
        never a symbol this app cannot safely size an order for.

        @details Reads current holdings fresh (`ITradingAccountReader.
        check_connection()`), never the stale figures `EnsureSessionReadyCommand`
        baselined at — the same "re-fetch, never trust a remembered value"
        principle every other reconciliation in this app already applies.
        A holding with no recorded baseline at all (`spot_baseline_holdings()`
        returns `None`) is the unrecoverable-unknown case: it could mean
        this app was never enabled on Spot this session, so the safe,
        conservative answer is to sell nothing rather than guess a baseline
        of zero and offer up the user's entire pre-existing holdings.

        `EPIC-029` ADR D6 r2 — each asset's sale is split per bot
        (`split_liquidation`): a bot's share, up to its inventory, carries
        its tag, so its inventory derived again afterwards is what is left.
        A split part below the exchange minimum is left held and reported
        as dust (`min_split_quantity`).
        """
        baseline = scope.session_state.spot_baseline_holdings()
        if baseline is None:
            return EmergencyStopStepResult(
                True,
                "No Spot holdings baseline recorded this session — nothing sold.",
            )

        status = scope.ports.account_reader.check_connection()
        if not status.reachable or status.holdings is None:
            return EmergencyStopStepResult(
                False, "Could not read current Spot holdings."
            )

        sold_assets: list[str] = []
        dust_assets: list[str] = []
        skipped_assets: list[str] = []
        for holding in status.holdings:
            if holding.asset == _QUOTE_ASSET or holding.is_dust:
                continue
            symbol = f"{holding.asset}{_QUOTE_ASSET}"
            metadata = scope.ports.metadata_provider.get_or_fetch(symbol)
            if metadata is None:
                # No exchange filters known for this symbol — cannot safely
                # size an order without guessing a step size
                # (`code/errors.md` #6, no fabricated fallback).
                skipped_assets.append(holding.asset)
                continue
            quantity = sellable_spot_quantity(
                holding.total,
                baseline.get(holding.asset, Decimal(0)),
                metadata.step_size_for(OrderType.MARKET),
            )
            if quantity <= 0:
                dust_assets.append(holding.asset)
                continue
            inventories = [
                (share.tag, share.inventory.quantity)
                for share in owner_shares
                if share.symbol == symbol
            ]
            parts = split_liquidation(
                quantity,
                inventories,
                metadata.step_size_for(OrderType.MARKET),
                min_split_quantity(scope.ports.book_ticker_reader, metadata)
                if inventories
                else Decimal(0),
            )
            if sum((part.quantity for part in parts), Decimal(0)) < quantity:
                dust_assets.append(holding.asset)
            if not parts:
                # Every part was dust: nothing was sold (the PR #320 re-review).
                continue
            try:
                for part in parts:
                    trading_client.place_order(
                        Order(
                            client_order_id=generate_client_order_id(part.tag),
                            symbol=symbol,
                            side=OrderSide.SELL,
                            order_type=OrderType.MARKET,
                            quantity=part.quantity,
                        )
                    )
                sold_assets.append(holding.asset)
            except Exception as exc:  # noqa: BLE001 - report every failure, never let one abort the remaining assets
                return EmergencyStopStepResult(
                    False,
                    f"Sold surplus on {len(sold_assets)} asset(s) — error selling "
                    f"{holding.asset}: {exc}.",
                )

        if not sold_assets and not dust_assets and not skipped_assets:
            return EmergencyStopStepResult(True, "No Spot holdings above the baseline.")
        message = f"Sold surplus on {len(sold_assets)} asset(s)."
        if dust_assets:
            message += (
                f" Dust remainder below the exchange minimum on: "
                f"{', '.join(sorted(dust_assets))}."
            )
        if skipped_assets:
            message += (
                f" Skipped (no exchange filters known): "
                f"{', '.join(sorted(skipped_assets))}."
            )
        return EmergencyStopStepResult(True, message)

    def _read_final_state(
        self, trading_client: ITradingClient
    ) -> tuple[tuple[LivePosition, ...], tuple[Order, ...], bool]:
        """@brief `BUG-093` — a best-effort read of the account's true
        state after the three steps above, regardless of their own
        outcome: a screen seeded its Positions/Open Orders
        tables before this command ran and has no other way to learn what
        actually happened — the user-data stream this screen otherwise
        relies on was already stopped in step 1.
        @return `(positions, open_orders, confirmed)` — `confirmed` is
        `False` only when this read itself failed; a caller must then
        treat the account's true state as unknown, never as "confirmed
        empty" from the accompanying empty tuples.
        """
        try:
            return (
                tuple(trading_client.get_positions()),
                tuple(trading_client.get_open_orders()),
                True,
            )
        except Exception as exc:  # noqa: BLE001 - best-effort, report via the bool
            logger.error("Could not confirm final account state: %s", exc)
            return (), (), False
