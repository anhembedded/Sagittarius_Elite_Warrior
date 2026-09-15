"""`IOrderSubmission`, implemented over the three use cases that already exist.

**Why it dispatches.** `ExecuteOrderCommandHandler` is the one place in this
app allowed to construct a live client (guarded by `ast` at an exact path),
and it holds `live_submission_guard()` across the whole
evaluate → submit → record sequence. A port that reimplemented any of that
would be a second order path; dispatching keeps exactly one, which is the
property `EPIC-024B` established when a human became the second real caller
alongside the strategy's tick.

**What it adds.** The published `OrderRequest` becomes the module's own
`PreviewOrderQuery`, and that is the whole translation. No gate, no limit, no
rounding is repeated here — this file would be the wrong place for any of
them, because the CLI's `trade-once` reaches the same handlers and would then
see different rules.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.cancel_order.command import (
    CancelOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.command import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order.query import (
    PreviewOrderQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.cancel_order_result import (
    CancelOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_submission import (
    IOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_preview import (
    OrderPreview,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    OrderRequest,
)


def _answered(response: object, expected: type) -> object:
    """See `TradingSessionService._answered` for why a wrong-typed answer
    raises instead of becoming a refusal the caller would show the user."""
    if not isinstance(response, expected):
        raise TypeError(
            f"the order dispatch was not answered with {expected.__name__} "
            f"but with {type(response).__name__} — no handler is bound for it"
        )
    return response


def _as_query(request: OrderRequest) -> PreviewOrderQuery:
    """The one translation this class performs. Field for field on purpose:
    `OrderRequest` was given `PreviewOrderQuery`'s exact shape (HLD §2.4 —
    every caller sets all six), so a mismatch here would be a typo rather
    than a design decision."""
    return PreviewOrderQuery(
        symbol=request.symbol,
        side=request.side,
        order_type=request.order_type,
        quantity=request.quantity,
        reference_price=request.reference_price,
        reduce_only=request.reduce_only,
    )


class OrderSubmissionService(IOrderSubmission):
    """The module's answer to "shape this order, and send it if I say so"."""

    def __init__(self, dispatcher: ICommandDispatcher) -> None:
        self._dispatcher = dispatcher

    def preview(self, request: OrderRequest) -> OrderPreview:
        response = self._dispatcher.dispatch(PreviewOrderQuery, _as_query(request))
        return _answered(response, OrderPreview)  # type: ignore[return-value]

    def submit(
        self, request: OrderRequest, *, live: bool = False
    ) -> ExecuteOrderResult:
        command = ExecuteOrderCommand(order_request=_as_query(request), live=live)
        response = self._dispatcher.dispatch(ExecuteOrderCommand, command)
        return _answered(response, ExecuteOrderResult)  # type: ignore[return-value]

    def cancel(self, symbol: str, client_order_id: str) -> CancelOrderResult:
        command = CancelOrderCommand(symbol=symbol, client_order_id=client_order_id)
        response = self._dispatcher.dispatch(CancelOrderCommand, command)
        return _answered(response, CancelOrderResult)  # type: ignore[return-value]
