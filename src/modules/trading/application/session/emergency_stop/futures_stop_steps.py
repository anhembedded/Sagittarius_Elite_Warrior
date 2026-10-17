"""`EPIC-039L` (decision D11, owner's O1) - the Futures steps of an Emergency Stop.

@details The order is the safety: (1) cancel the **regular** orders, so the ladder cannot refill
while a position is closed; (2) close every position; (3) cancel the **conditional** orders of each
symbol that is **confirmed flat** by a fresh read and has no regular order still resting. A
protective stop that stands over a position the close did not take down stays standing, and the
result says so: a failed close must never leave a position with neither the bot nor a stop watching
it. A close-all stop over a flat symbol is
cancelled, because it could open a position.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.resolve_unknown_outcome import (
    place_resolving_unknown,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop.unconfirmed_orders import (
    closing_order_for,
    unconfirmed_close,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.emergency_stop_result import (
    EmergencyStopStepResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_outcome_unknown import (
    OrderOutcomeUnknownError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import (
    TRIGGERED_ORDER_TYPES,
)

logger = logging.getLogger("App.CommandHandler")

#: A venue with nothing conditional to cancel (Spot) answers this.
NO_CONDITIONAL_ORDERS = EmergencyStopStepResult(True, "No conditional orders.")


def cancel_regular_orders(trading_client: ITradingClient) -> EmergencyStopStepResult:
    """Step 2: every symbol's regular orders; its conditional ones stand until step 4."""
    try:
        open_orders = trading_client.get_open_orders()
    except Exception as exc:  # noqa: BLE001 - one step failing must not abort the next
        return EmergencyStopStepResult(False, f"Error reading open orders: {exc}")
    open_orders = [order for order in open_orders if not _is_conditional(order)]
    symbols = sorted({order.symbol for order in open_orders})
    if not symbols:
        return EmergencyStopStepResult(True, "No open orders.")
    cancelled = 0
    for symbol in symbols:
        try:
            cancelled += len(trading_client.cancel_regular_orders(symbol))
        except Exception as exc:  # noqa: BLE001
            remaining = len(open_orders) - cancelled
            return EmergencyStopStepResult(
                False,
                f"Cancelled {cancelled}/{len(open_orders)} open orders - error on "
                f"{symbol}: {exc}. {remaining} orders still not cancelled.",
            )
    return EmergencyStopStepResult(
        True,
        f"Cancelled {cancelled} open orders; stop orders stand until their position is flat.",
    )


def close_all_futures_positions(
    trading_client: ITradingClient,
) -> EmergencyStopStepResult:
    """Step 3: a reduce-only market order against every position."""
    try:
        positions = trading_client.get_positions()
    except Exception as exc:  # noqa: BLE001
        return EmergencyStopStepResult(False, f"Error reading positions: {exc}")
    if not positions:
        return EmergencyStopStepResult(True, "No open positions.")

    closed_count = 0
    unconfirmed: list[str] = []
    for position in positions:
        try:
            place_resolving_unknown(trading_client, closing_order_for(position))
            closed_count += 1
        except OrderOutcomeUnknownError:
            unconfirmed.append(position.symbol)
        except Exception as exc:  # noqa: BLE001
            remaining = len(positions) - closed_count
            return EmergencyStopStepResult(
                False,
                f"Closed {closed_count}/{len(positions)} positions - error on "
                f"{position.symbol}: {exc}. {remaining} positions still open.",
            )
    if unconfirmed:
        return unconfirmed_close(closed_count, len(positions), unconfirmed)
    return EmergencyStopStepResult(True, f"Closed {closed_count} positions.")


def cancel_conditional_orders_of_flat_symbols(
    trading_client: ITradingClient,
) -> EmergencyStopStepResult:
    """Step 4: the conditional orders of each symbol a fresh read shows flat."""
    try:
        open_orders = trading_client.get_open_orders()
        conditional = {order.symbol for order in open_orders if _is_conditional(order)}
        if not conditional:
            return NO_CONDITIONAL_ORDERS
        held = {position.symbol for position in trading_client.get_positions()}
    except Exception as exc:  # noqa: BLE001 - unread is not flat: every stop stays
        logger.error(
            "Emergency stop: stop orders kept, the account was not read: %s", exc
        )
        return EmergencyStopStepResult(
            False, f"Stop orders left standing, the account could not be read: {exc}"
        )
    # A symbol whose ladder still rests (step 2 failed there) is not safe: a fill reopens a position.
    laddered = {order.symbol for order in open_orders if not _is_conditional(order)}
    kept = sorted(conditional & (held | laddered))
    cancelled = 0
    for symbol in sorted(conditional - held - laddered):
        try:
            cancelled += len(trading_client.cancel_conditional_orders(symbol))
        except Exception as exc:  # noqa: BLE001
            return EmergencyStopStepResult(
                False,
                f"Cancelled {cancelled} stop orders - error on {symbol}: {exc}. "
                "A stop may still stand over a flat symbol.",
            )
    detail = f"Cancelled {cancelled} stop orders over flat symbols."
    if kept:
        logger.error("Emergency stop: stop orders kept over open positions on %s", kept)
        return EmergencyStopStepResult(
            False,
            f"{detail} Kept over a position or a ladder that is still open: {', '.join(kept)}.",
        )
    return EmergencyStopStepResult(True, detail)


def _is_conditional(order: Order) -> bool:
    """A conditional order: a stop that waits for its trigger price (Futures algo orders)."""
    return order.close_position or order.order_type in TRIGGERED_ORDER_TYPES
