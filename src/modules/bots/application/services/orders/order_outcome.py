"""`EPIC-029E` — what trading answered to one of a bot's orders, as a value (ADR D9).

Split from `bot_order_gateway.py` (the 400-line ceiling): the outcome types and the
rules that classify an answer, an exception or a refusal into one. The gateway
sends and receives; this module says what each answer means to the lifecycle. The
gateway re-exports `OrderOutcome`, `OrderOutcomeKind` and `SWITCH_OFF_GATES`, so
the importers that named them there are unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.cancel_order_result import (
    CancelOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderNotionalRejection,
    ExecuteOrderPriceRejection,
    ExecuteOrderResult,
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
    OrderRejectionReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    TradingLimitViolation,
)

#: The refusals that mean "trading is off", not "this order is wrong" (D9).
SWITCH_OFF_GATES: frozenset[ExecuteOrderSafetyGate] = frozenset(
    {
        ExecuteOrderSafetyGate.TRADING_SWITCH_OFF,
        ExecuteOrderSafetyGate.CONNECTION_NOT_READY,
    }
)


class OrderOutcomeKind(str, Enum):
    DONE = "done"
    SWITCH_OFF = "switch_off"
    REFUSED = "refused"
    RATE_LIMITED = "rate_limited"
    #: `BUG-254` - trading judged the order sooner than the owner budget's spacing after the
    #: previous one: "not yet", never "no". The gateway waits another turn and sends it again
    #: (`BotOrderGateway._submit_paced`), and answers `RATE_LIMITED` when the retries are spent,
    #: so no caller sees this kind.
    PACED = "paced"
    SYMBOL_NOT_TRADING = "symbol_not_trading"
    SYMBOL_NOT_LISTED = "symbol_not_listed"
    #: The order's own numbers were refused (`EPIC-035T`): a quantity, a price
    #: band, the minimum notional, a plain `-2010`. About one order, not the bot
    #: or the venue: a RUNNING ladder leaves that rung EMPTY and goes on.
    ORDER_INVALID = "order_invalid"
    KEY_REJECTED = "key_rejected"
    #: A cancel found no such order: it filled or ended first. Not `DONE` (nothing was
    #: cancelled, and a protective stop's record tells a cancel from an end), not a fault: a
    #: ladder's cancel has met its goal, which is that the order no longer rests.
    GONE = "gone"
    FAULT = "fault"


@dataclass(frozen=True, slots=True)
class OrderOutcome:
    """What trading answered: done (with the order's id) or why not."""

    kind: OrderOutcomeKind
    client_order_id: str = ""
    detail: str = ""
    #: For `RATE_LIMITED`: how long the exchange asked for.
    retry_after: timedelta | None = None
    #: For `DONE`: the quantity the exchange accepted (`BUG-205`), which a ladder
    #: saves and shows instead of the quantity it asked for.
    quantity: Decimal | None = None

    @property
    def done(self) -> bool:
        return self.kind is OrderOutcomeKind.DONE


#: The exchange's refusals that are about the symbol, the key or the order's own
#: numbers: each is a named outcome, every other rejection stays a fault.
_NAMED_REFUSALS: dict[OrderRejectionReason, OrderOutcomeKind] = {
    OrderRejectionReason.LOT_SIZE: OrderOutcomeKind.ORDER_INVALID,
    OrderRejectionReason.MIN_NOTIONAL: OrderOutcomeKind.ORDER_INVALID,
    OrderRejectionReason.PRICE_FILTER: OrderOutcomeKind.ORDER_INVALID,
    OrderRejectionReason.NEW_ORDER_REJECTED: OrderOutcomeKind.ORDER_INVALID,
    OrderRejectionReason.KEY_REJECTED: OrderOutcomeKind.KEY_REJECTED,
    OrderRejectionReason.SYMBOL_NOT_TRADING: OrderOutcomeKind.SYMBOL_NOT_TRADING,
    OrderRejectionReason.SYMBOL_NOT_LISTED: OrderOutcomeKind.SYMBOL_NOT_LISTED,
}


def named_rejection(exc: Exception) -> OrderOutcome | None:
    """The outcome a refusal about the symbol, the key or the order's numbers is,
    or `None` for any other failure, which stays a fault. The exchange's own text
    is kept: it is a short sentence, never a URL (`describe_failure`)."""
    if not isinstance(exc, OrderRejectedByExchangeError):
        return None
    kind = _NAMED_REFUSALS.get(exc.reason)
    if kind is None:
        return None
    return OrderOutcome(kind, detail=exc.raw_message)


def is_order_gone(exc: Exception) -> bool:
    """Whether `exc` is the exchange saying it holds no such order: a cancel of an order that
    already filled or ended is `GONE`, not a fault."""
    return (
        isinstance(exc, OrderRejectedByExchangeError)
        and exc.reason is OrderRejectionReason.UNKNOWN_ORDER
    )


def gone_outcome(client_order_id: str) -> OrderOutcome:
    """A cancel that found the order gone; its fill, if any, arrives as an event."""
    return OrderOutcome(
        OrderOutcomeKind.GONE, client_order_id, "the exchange holds no such order"
    )


def fault_text(exc: Exception) -> str:
    """What the bot's state line says of a request that raised: its kind, never
    its text, which is an exchange's or a library's (`BOT-169`); the exception
    is in the log (`logger.exception` at each caller)."""
    return f"the request failed ({type(exc).__name__}); see the log"


def classify_submit(result: ExecuteOrderResult) -> OrderOutcome:
    if result.blocked_by is not None:
        return pacing_outcome(result) or _refusal(result.blocked_by, "")
    if result.submitted_order is None:
        return OrderOutcome(OrderOutcomeKind.FAULT, detail="trading returned no order")
    accepted = result.submitted_order
    return OrderOutcome(
        OrderOutcomeKind.DONE, accepted.client_order_id, quantity=accepted.quantity
    )


def classify_cancel(result: CancelOrderResult, client_order_id: str) -> OrderOutcome:
    if result.blocked_by is not None:
        return _refusal(result.blocked_by, client_order_id)
    if result.already_gone:
        return gone_outcome(client_order_id)
    return OrderOutcome(OrderOutcomeKind.DONE, client_order_id)


def _refusal(blocked_by: Enum, client_order_id: str) -> OrderOutcome:
    if blocked_by in SWITCH_OFF_GATES:
        kind = OrderOutcomeKind.SWITCH_OFF
    elif blocked_by is ExecuteOrderSafetyGate.KEY_REJECTED:
        kind = OrderOutcomeKind.KEY_REJECTED
    elif isinstance(
        blocked_by, ExecuteOrderNotionalRejection | ExecuteOrderPriceRejection
    ):
        kind = OrderOutcomeKind.ORDER_INVALID
    else:
        kind = OrderOutcomeKind.REFUSED
    return OrderOutcome(kind, client_order_id, str(blocked_by.value))


def pacing_outcome(result: ExecuteOrderResult) -> OrderOutcome | None:
    """`BUG-254` - the outcome of a refusal by the app's own pacing, or `None` for any other.

    The owner budget's spacing and rate are the app's own speed limits (ADR D6 checks 4 and 5),
    not a verdict on the order or the venue: the order is sound and was only sent too soon. Too
    soon after the previous order is `PACED` (retry_after: what the policy found missing, from the
    facts it judged); too many in the window is `RATE_LIMITED`, for the budget's window, the longest
    the oldest send of it can still count. Treating either as `REFUSED` halted a start and sold
    its position at market."""
    violation = result.blocked_by
    facts = None if result.limit_context is None else result.limit_context.owner_budget
    if violation is TradingLimitViolation.OWNER_BUDGET_SPACING:
        missing = None
        if facts is not None and facts.time_since_last_order is not None:
            missing = max(
                facts.budget.min_order_spacing - facts.time_since_last_order,
                timedelta(0),
            )
        return OrderOutcome(
            OrderOutcomeKind.PACED, detail=violation.value, retry_after=missing
        )
    if violation is TradingLimitViolation.OWNER_BUDGET_RATE:
        return OrderOutcome(
            OrderOutcomeKind.RATE_LIMITED,
            detail=f"the app's own order budget: {violation.value}",
            retry_after=None if facts is None else facts.budget.window,
        )
    return None
