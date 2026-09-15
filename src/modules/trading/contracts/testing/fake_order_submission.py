"""`FakeOrderSubmission` — `IOrderSubmission`'s verified fake.

A test says what the module would answer and reads back **what was asked**,
which for this port is the part that matters: every request is recorded, so a
consumer test can assert that a dry run stayed a dry run.

@par The one guarantee this fake exists to protect
`submit(request, live=False)` is a real dry run — every gate evaluated,
nothing sent. A `Mock(spec=IOrderSubmission)` records the call and answers
whatever it was told, so a consumer that passed `live=True` by mistake would
still see the test pass. `submitted_live`, `submitted_dry` and `validated` are
three separate lists precisely so that mistake cannot hide: nothing sent, sent
to the venue's test endpoint, and sent for real are three different things.
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
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
        self._validate: Order | None = None
        self._validate_error: Exception | None = None
        self._submit_error: Exception | None = None
        #: Every request passed to `preview()`, in order.
        self.previewed: list[OrderRequest] = []
        #: Requests submitted with `live=True` — the list a test asserts is
        #: EMPTY when it expected a dry run.
        self.submitted_live: list[OrderRequest] = []
        #: Requests submitted with `live=False`.
        self.submitted_dry: list[OrderRequest] = []
        #: `(symbol, client_order_id)` pairs passed to `cancel()`.
        self.cancelled: list[tuple[str, str]] = []
        #: Every request passed to `validate()` — kept apart from both submit
        #: lists because a dry run against the venue's test endpoint creates
        #: nothing, and a test that confused it with a live submission would
        #: be asserting the opposite of what it means to.
        self.validated: list[OrderRequest] = []

    def preview_answers(self, preview: OrderPreview) -> None:
        self._preview = preview

    def submit_answers(self, result: ExecuteOrderResult) -> None:
        self._submit = result

    def cancel_answers(self, result: CancelOrderResult) -> None:
        self._cancel = result

    def submit_raises(self, error: Exception) -> None:
        """Makes `submit()` raise instead of answering.

        A refusal is a value on `ExecuteOrderResult`, never an exception — but
        the venue can still reject the order it actually received
        (`OrderRejectedByExchangeError`) or the request can fail in transit,
        and a caller that lets either escape is a defect: `BUG-090` is the
        report where one rejected order took down tick processing for the rest
        of the session. The request is still recorded, because "it was sent and
        refused" is a different fact from "it was never sent".
        """
        self._submit_error = error

    def validate_answers(self, order: Order) -> None:
        self._validate = order

    def validate_raises(self, error: Exception) -> None:
        """`validate()` reports by raising, so a test that wants the failure
        path says which failure — an exchange refusal, an order this app
        built wrong, or a transport error are three different messages the
        caller prints."""
        self._validate_error = error

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
        if self._submit_error is not None:
            raise self._submit_error
        if self._submit is None:
            raise AssertionError(
                "FakeOrderSubmission.submit() was called before "
                "submit_answers() said what to answer — see preview() above "
                "for why there is no default"
            )
        return self._submit

    def validate(self, request: OrderRequest) -> Order:
        self.validated.append(request)
        if self._validate_error is not None:
            raise self._validate_error
        if self._validate is None:
            raise AssertionError(
                "FakeOrderSubmission.validate() was called before "
                "validate_answers() or validate_raises() said what to do — "
                "see preview() above for why there is no default"
            )
        return self._validate

    def cancel(self, symbol: str, client_order_id: str) -> CancelOrderResult:
        self.cancelled.append((symbol, client_order_id))
        if self._cancel is None:
            raise AssertionError(
                "FakeOrderSubmission.cancel() was called before "
                "cancel_answers() said what to answer"
            )
        return self._cancel
