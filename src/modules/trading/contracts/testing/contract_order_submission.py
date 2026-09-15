"""The contract suite for `IOrderSubmission` (HLD §10.3).

Four guarantees, and all four are about the difference between asking and
sending — which is the only thing every consumer of this port shares:

1. `submit(request, live=False)` is a **real** dry run: the request is
   evaluated and nothing is sent. This is the guarantee a `Mock` cannot keep,
   because a mock records `live=True` and answers exactly the same;
2. `submit(request, live=True)` does send, so the two cases are
   distinguishable at all;
3. `preview()` never sends, whatever the request says;
4. `validate()` never sends a **live** order, although it does reach the
   venue. This is the one a reader is most likely to doubt, and the one whose
   failure would be worst: `order-dry-run` exists to be safe to run before
   trading is ever turned on.

What the suite does **not** pin is the rounding, the gates or the limits. Those
are `ExecuteOrderCommandHandler`'s and `TradingLimitPolicy`'s own tests: the
port promises to run them, not to define them, and a guarantee restated in two
places is a guarantee that can disagree with itself.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_submission import (
    IOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    OrderRequest,
)

#: How a subclass asks its implementation "what did you actually send?" —
#: the fake reads its own lists, the real one inspects the dispatcher's spy.
type SentLive = Callable[[], tuple[OrderRequest, ...]]


class OrderSubmissionContract:
    """Inherit this, provide `impl` and `sent_live`. Both must pass it."""

    @pytest.fixture
    def impl(self) -> IOrderSubmission:
        raise NotImplementedError(
            "an OrderSubmissionContract subclass must provide an `impl` fixture"
        )

    @pytest.fixture
    def sent_live(self) -> SentLive:
        raise NotImplementedError(
            "an OrderSubmissionContract subclass must provide a `sent_live` "
            "fixture reporting which requests were submitted live"
        )

    def test_a_dry_run_sends_nothing(
        self, impl: IOrderSubmission, sent_live: SentLive, request_btc: OrderRequest
    ) -> None:
        impl.submit(request_btc)

        assert sent_live() == ()

    def test_a_live_submission_sends(
        self, impl: IOrderSubmission, sent_live: SentLive, request_btc: OrderRequest
    ) -> None:
        """Without this, the test above would pass against an implementation
        that never sends anything at all."""
        impl.submit(request_btc, live=True)

        assert sent_live() == (request_btc,)

    def test_a_preview_sends_nothing(
        self, impl: IOrderSubmission, sent_live: SentLive, request_btc: OrderRequest
    ) -> None:
        impl.preview(request_btc)

        assert sent_live() == ()

    def test_a_validation_never_sends_a_live_order(
        self, impl: IOrderSubmission, sent_live: SentLive, request_btc: OrderRequest
    ) -> None:
        """`validate()` reaches the exchange — `POST /fapi/v1/order/test` —
        and must still create nothing. An implementation that routed it to
        the real endpoint would pass every other test in this suite."""
        impl.validate(request_btc)

        assert sent_live() == ()
