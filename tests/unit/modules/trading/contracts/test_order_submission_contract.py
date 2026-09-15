"""`IOrderSubmission`'s contract, against its verified fake (HLD §10.3).

The real `OrderSubmissionService` runs the same suite once PR 1.3c registers
the three handlers inside the module — `ExecuteOrderCommandHandler` is the one
file allowed to build a live client, and it takes the `ExchangeSessionFactory`
instance still shared with `market_data`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.cancel_order_result import (
    CancelOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_preview import (
    OrderPreview,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    OrderRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.contract_order_submission import (
    OrderSubmissionContract,
    SentLive,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_submission import (
    FakeOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.order_quantity_rounding_policy import (
    NotionalCheck,
)


@pytest.fixture
def request_btc() -> OrderRequest:
    return OrderRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.005"),
        reference_price=Decimal(64000),
    )


def _order() -> Order:
    return Order(
        client_order_id=ClientOrderId("sew-1"),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.005"),
        order_time=datetime(2026, 9, 15, tzinfo=UTC),
    )


def _preview() -> OrderPreview:
    return OrderPreview(
        order=_order(),
        raw_quantity=Decimal("0.005"),
        estimated_notional=Decimal(320),
        min_notional=Decimal(100),
        step_size=Decimal("0.001"),
        notional_check=NotionalCheck.SUFFICIENT,
    )


class TestTheFake(OrderSubmissionContract):
    @pytest.fixture
    def impl(self) -> FakeOrderSubmission:
        fake = FakeOrderSubmission()
        fake.preview_answers(_preview())
        fake.submit_answers(
            ExecuteOrderResult(
                blocked_by=None,
                preview=_preview(),
                limit_checks=(),
                submitted_order=_order(),
            )
        )
        return fake

    @pytest.fixture
    def sent_live(self, impl: FakeOrderSubmission) -> SentLive:
        def sent() -> tuple[OrderRequest, ...]:
            return tuple(impl.submitted_live)

        return sent


class TestTheFakesOwnBookkeeping:
    """`BUG-120` — the three `*_answers()` helpers and the four records."""

    def test_a_missing_answer_is_a_loud_failure_not_a_default(self) -> None:
        """An `OrderPreview` has no meaningful default. Inventing one would
        let a caller's rounding assertions pass against numbers nobody chose,
        which is `BUG-120`'s shape exactly."""
        fake = FakeOrderSubmission()

        with pytest.raises(AssertionError, match="preview_answers"):
            fake.preview(
                OrderRequest(
                    symbol="BTCUSDT",
                    side=OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    quantity=Decimal(1),
                    reference_price=Decimal(1),
                )
            )

    def test_preview_answers_is_what_comes_back(
        self, request_btc: OrderRequest
    ) -> None:
        fake = FakeOrderSubmission()
        preview = _preview()
        fake.preview_answers(preview)

        assert fake.preview(request_btc) is preview
        assert fake.previewed == [request_btc]

    def test_submit_answers_is_what_comes_back(self, request_btc: OrderRequest) -> None:
        fake = FakeOrderSubmission()
        result = ExecuteOrderResult(
            blocked_by=ExecuteOrderSafetyGate.TRADING_SWITCH_OFF,
            preview=None,
            limit_checks=(),
            submitted_order=None,
        )
        fake.submit_answers(result)

        assert fake.submit(request_btc) is result

    def test_cancel_answers_is_what_comes_back_and_the_keys_are_recorded(self) -> None:
        fake = FakeOrderSubmission()
        result = CancelOrderResult(blocked_by=None, cancelled_order=_order())
        fake.cancel_answers(result)

        assert fake.cancel("BTCUSDT", "sew-1") is result
        assert fake.cancelled == [("BTCUSDT", "sew-1")]

    def test_live_and_dry_submissions_land_in_different_lists(
        self, request_btc: OrderRequest
    ) -> None:
        """The guarantee the whole fake exists for: a consumer that passed
        `live=True` by mistake cannot hide behind a recorded call."""
        fake = FakeOrderSubmission()
        fake.submit_answers(
            ExecuteOrderResult(
                blocked_by=None, preview=None, limit_checks=(), submitted_order=None
            )
        )

        fake.submit(request_btc)
        fake.submit(request_btc, live=True)

        assert fake.submitted_dry == [request_btc]
        assert fake.submitted_live == [request_btc]
