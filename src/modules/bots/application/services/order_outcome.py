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
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.cancel_order_result import (
    CancelOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
    OrderRejectionReason,
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
    SYMBOL_NOT_TRADING = "symbol_not_trading"
    SYMBOL_NOT_LISTED = "symbol_not_listed"
    KEY_REJECTED = "key_rejected"
    FAULT = "fault"


@dataclass(frozen=True, slots=True)
class OrderOutcome:
    """What trading answered: done (with the order's id) or why not."""

    kind: OrderOutcomeKind
    client_order_id: str = ""
    detail: str = ""
    #: For `RATE_LIMITED`: how long the exchange asked for.
    retry_after: timedelta | None = None

    @property
    def done(self) -> bool:
        return self.kind is OrderOutcomeKind.DONE


#: The exchange's refusals that are about the symbol or the key, not about the
#: order: each is a named outcome, every other rejection stays a fault.
_NAMED_REFUSALS: dict[OrderRejectionReason, OrderOutcomeKind] = {
    OrderRejectionReason.KEY_REJECTED: OrderOutcomeKind.KEY_REJECTED,
    OrderRejectionReason.SYMBOL_NOT_TRADING: OrderOutcomeKind.SYMBOL_NOT_TRADING,
    OrderRejectionReason.SYMBOL_NOT_LISTED: OrderOutcomeKind.SYMBOL_NOT_LISTED,
}


def named_rejection(exc: Exception) -> OrderOutcome | None:
    """The outcome a refusal about the symbol or the key is, or `None` for any other
    failure, which stays a fault. The exchange's own text is kept: it is a
    short sentence, never a URL (`describe_failure`)."""
    if not isinstance(exc, OrderRejectedByExchangeError):
        return None
    kind = _NAMED_REFUSALS.get(exc.reason)
    if kind is None:
        return None
    return OrderOutcome(kind, detail=exc.raw_message)


def fault_text(exc: Exception) -> str:
    """What the bot's state line says of a request that raised: its kind, never
    its text, which is an exchange's or a library's (`BOT-169`); the exception
    is in the log (`logger.exception` at each caller)."""
    return f"the request failed ({type(exc).__name__}); see the log"


def classify_submit(result: ExecuteOrderResult) -> OrderOutcome:
    if result.blocked_by is not None:
        return _refusal(result.blocked_by, "")
    if result.submitted_order is None:
        return OrderOutcome(OrderOutcomeKind.FAULT, detail="trading returned no order")
    return OrderOutcome(OrderOutcomeKind.DONE, result.submitted_order.client_order_id)


def classify_cancel(result: CancelOrderResult, client_order_id: str) -> OrderOutcome:
    if result.blocked_by is not None:
        return _refusal(result.blocked_by, client_order_id)
    return OrderOutcome(OrderOutcomeKind.DONE, client_order_id)


def _refusal(blocked_by: Enum, client_order_id: str) -> OrderOutcome:
    if blocked_by in SWITCH_OFF_GATES:
        kind = OrderOutcomeKind.SWITCH_OFF
    elif blocked_by is ExecuteOrderSafetyGate.KEY_REJECTED:
        kind = OrderOutcomeKind.KEY_REJECTED
    else:
        kind = OrderOutcomeKind.REFUSED
    return OrderOutcome(kind, client_order_id, str(blocked_by.value))
