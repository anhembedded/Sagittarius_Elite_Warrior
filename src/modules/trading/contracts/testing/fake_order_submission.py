"""`FakeOrderSubmission` — `IOrderSubmission`'s verified fake.

A test says what the module would answer and reads back **what was asked**,
which for this port is the part that matters: every request is recorded, so a
consumer test can assert that a dry run stayed a dry run.

@par The one guarantee this fake exists to protect
`submit(request, live=False)` is a real dry run — every gate evaluated,
nothing sent. A `Mock(spec=IOrderSubmission)` records the call and answers
whatever it was told, so a consumer that passed `live=True` by mistake would
still see the test pass. `submitted_live` and `submitted_dry` are separate
lists here precisely so that mistake cannot hide.
"""

from __future__ import annotations

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


class FakeOrderSubmission(IOrderSubmission):
    """The answers a test says the module gives, and a record of the asking."""

    def __init__(self) -> None:
        self._preview: OrderPreview | None = None
        self._submit: ExecuteOrderResult | None = None
        self._cancel: CancelOrderResult | None = None
        #: Every request passed to `preview()`, in order.
        self.previewed: list[OrderRequest] = []
        #: Requests submitted with `live=True` — the list a test asserts is
        #: EMPTY when it expected a dry run.
        self.submitted_live: list[OrderRequest] = []
        #: Requests submitted with `live=False`.
        self.submitted_dry: list[OrderRequest] = []
        #: `(symbol, client_order_id)` pairs passed to `cancel()`.
        self.cancelled: list[tuple[str, str]] = []

    def preview_answers(self, preview: OrderPreview) -> None:
        self._preview = preview

    def submit_answers(self, result: ExecuteOrderResult) -> None:
        self._submit = result

    def cancel_answers(self, result: CancelOrderResult) -> None:
        self._cancel = result

    def preview(self, request: OrderRequest) -> OrderPreview:
        self.previewed.append(request)
        if self._preview is None:
            raise AssertionError(
                "FakeOrderSubmission.preview() was called before "
                "preview_answers() said what to answer — an OrderPreview has "
                "no meaningful default, and inventing one would let a caller's "
                "rounding assertions pass against numbers nobody chose"
            )
        return self._preview

    def submit(
        self, request: OrderRequest, *, live: bool = False
    ) -> ExecuteOrderResult:
        (self.submitted_live if live else self.submitted_dry).append(request)
        if self._submit is None:
            raise AssertionError(
                "FakeOrderSubmission.submit() was called before "
                "submit_answers() said what to answer — see preview() above "
                "for why there is no default"
            )
        return self._submit

    def cancel(self, symbol: str, client_order_id: str) -> CancelOrderResult:
        self.cancelled.append((symbol, client_order_id))
        if self._cancel is None:
            raise AssertionError(
                "FakeOrderSubmission.cancel() was called before "
                "cancel_answers() said what to answer"
            )
        return self._cancel
