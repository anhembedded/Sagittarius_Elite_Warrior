"""Port: *shape, check and send one order* (HLD §3.4).

**Why this port exists.** `EPIC-024B` proved that every order this app can
place goes through three use cases — preview, execute, cancel — and nothing
else may reach `ITradingClient`. But the callers reached them by building
`PreviewOrderQuery` / `ExecuteOrderCommand` / `CancelOrderCommand` and
dispatching, so five files in the legacy tree imported this module's
`application/` package: the boundary rule's one prohibition. They call this
port instead, and the commands stay where they belong.

**The safety pipeline is not this port's to re-state.** `submit()` runs the
same three gates and four limits `ExecuteOrderCommandHandler` has always run,
holding the same `live_submission_guard()` across evaluate → submit → record
(`EPIC-024B`, `BUG-090`). The port adds a name and a type; it adds no rule and
removes none. `live=False` is still the default and still stops before any
order-submission network call.

@par The seam, and what it is for (`architecture-rule.md` §7.2.1)
Plausible next consumers, and why each is a local change:

- **A second automated caller** — another bot, copy-trading. It calls
  `submit()` with its own `owner_id`-tagged request once Phase 2 adds the
  symbol lease; nothing here changes shape.
- **A bracket / OCO order** — a second `order_type` value and a second branch
  inside the module's own shaping, not a second port.
- **A venue that prices in the quote asset** — `reference_price` already
  carries the number the caller decided against, so the conversion stays
  inside the adapter that knows the venue.

What is **not** local, and is written down rather than pretended away: a
partial fill stream. `ExecuteOrderResult` answers once, for one submission;
watching an order fill over time is `OrderFilledEvent`'s job, and a caller
that needs both today has to correlate them by `client_order_id`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.cancel_order_result import (
    CancelOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_preview import (
    OrderPreview,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    OrderRequest,
)


class IOrderSubmission(ABC):
    """The only way to send an order, to ask what one would look like before
    sending it, and to have the venue check one without creating it."""

    @abstractmethod
    def preview(self, request: OrderRequest) -> OrderPreview:
        """What this order becomes after the exchange's filters are applied.

        No network call places anything; the module may fetch symbol metadata
        to round with. `OrderPreview.notional_check` is how a caller learns
        the order is below the venue's minimum **before** submitting —
        `BUG-090`: letting it round-trip for a `-4164` rejection is what this
        replaces.
        """

    @abstractmethod
    def submit(
        self, request: OrderRequest, *, live: bool = False
    ) -> ExecuteOrderResult:
        """Run the full safety pipeline and, when `live`, place the order.

        `live=False` is the default and is a **real** dry run: every gate and
        limit is evaluated against live data, and nothing is sent. Always
        answers; a refusal is a named value on the result
        (`ExecuteOrderSafetyGate`, a `TradingLimitViolation`, or
        `ExecuteOrderNotionalRejection`), never an exception a caller must
        anticipate.
        """

    @abstractmethod
    def validate(self, request: OrderRequest) -> Order:
        """Send this order to the venue's **test** endpoint and return the
        normalized order it accepted.

        The third thing a caller can do with an order, and genuinely distinct
        from the other two: `preview()` makes no network call at all, and
        `submit(live=False)` evaluates every gate and limit against live data
        and then stops. This one reaches the exchange — `POST
        /fapi/v1/order/test` — and so is the only way to learn that the
        signature, the key's permissions and the payload are all actually
        right, while creating nothing. It is what `order-dry-run` has always
        done, and `EPIC-021F` called it that epic's most important milestone
        for exactly that reason.

        Raises rather than answering with a result, and deliberately: this is
        a diagnostic, so a caller wants the specific failure, not a summary.
        `OrderRejectedByExchangeError` when the venue refuses,
        `InvalidOrderForSubmissionError` when this app built an order that
        does not satisfy the symbol's filters, and a transport exception when
        the request never arrived. The safety pipeline is **not** run: a dry
        run is not gated on the trading switch, which is the whole point of
        being able to run it before turning trading on.
        """

    @abstractmethod
    def cancel(self, symbol: str, client_order_id: str) -> CancelOrderResult:
        """Cancel one open order this app placed.

        Keyed by the client order id rather than the exchange's, because that
        is the id this app generated and the only one it can be sure of
        (`ClientOrderId`). Answers with `cancelled_order=None` and a named
        `blocked_by` when a gate refused.
        """
