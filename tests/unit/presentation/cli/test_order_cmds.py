"""`order-preview` and `order-dry-run`, the two headless order commands.

Neither had a test of its own before `EPIC-025` PR 1.3c-2 — only their
formatters did, which cover how a result is printed and say nothing about
whether the command asks the right thing. Both files were just rewired onto
`IOrderSubmission`, so this is where that wiring is held: `order-preview`
must never reach the venue at all, and `order-dry-run` must validate the
order *it previewed*, which is the guarantee that makes it safe to run before
trading is ever turned on.

`FakeOrderSubmission` rather than a mock, for the reason HLD §10.3 rule 4
gives: it keeps previews, dry runs, venue validations and live submissions in
four separate records, so "this command sent a live order by mistake" is a
failing assertion here rather than an indistinguishable recorded call.
"""

from __future__ import annotations

import json
from argparse import Namespace
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_submission import (
    IOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.invalid_order_for_submission import (
    InvalidOrderForSubmissionError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_preview import (
    OrderPreview,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
    OrderRejectionReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_submission import (
    FakeOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.order_quantity_rounding_policy import (
    NotionalCheck,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.order_dry_run_cmd import (
    execute_order_dry_run,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.order_preview_cmd import (
    execute_order_preview,
)
from sagittarius_engine import App

_SYMBOL = "BTCUSDT"


def _args(**overrides: object) -> Namespace:
    base: dict[str, object] = {
        "symbol": _SYMBOL,
        "side": "BUY",
        "type": "MARKET",
        "qty": "0.005",
        "price": "64000",
        "json": False,
    }
    base.update(overrides)
    return Namespace(**base)


def _order() -> Order:
    return Order(
        client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
        symbol=_SYMBOL,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.005"),
        status=OrderStatus.NEW,
        order_time=datetime(2026, 9, 15, tzinfo=UTC),
    )


def _preview() -> OrderPreview:
    return OrderPreview(
        order=_order(),
        raw_quantity=Decimal("0.0051"),
        estimated_notional=Decimal(320),
        min_notional=Decimal(100),
        step_size=Decimal("0.001"),
        notional_check=NotionalCheck.SUFFICIENT,
    )


@pytest.fixture
def submission() -> FakeOrderSubmission:
    fake = FakeOrderSubmission()
    fake.preview_answers(_preview())
    fake.validate_answers(_order())
    return fake


@pytest.fixture
def app(submission: FakeOrderSubmission) -> Mock:
    app = Mock(spec=App)

    def resolve(interface: object) -> object:
        if interface is IOrderSubmission:
            return submission
        return Mock()

    app.container.resolve.side_effect = resolve
    return app


class TestOrderPreview:
    def test_it_previews_the_requested_order_and_sends_nothing(
        self, app: Mock, submission: FakeOrderSubmission, capsys
    ) -> None:
        execute_order_preview(app, _args())

        (request,) = submission.previewed
        assert request.symbol == _SYMBOL
        assert request.side is OrderSide.BUY
        assert request.order_type is OrderType.MARKET
        assert request.quantity == Decimal("0.005")
        assert request.reference_price == Decimal(64000)
        # The whole promise of this command: nothing reached the venue, by
        # either route.
        assert submission.validated == []
        assert submission.submitted_live == []
        assert submission.submitted_dry == []
        assert _SYMBOL in capsys.readouterr().out

    def test_json_prints_the_normalized_order_as_json(
        self, app: Mock, submission: FakeOrderSubmission, capsys
    ) -> None:
        execute_order_preview(app, _args(json=True))

        printed = json.loads(capsys.readouterr().out)
        assert printed["order"]["symbol"] == _SYMBOL
        # The normalized quantity, not the one the actor typed — which is the
        # reason `--json` exists (`order_preview_to_dict`'s own docstring).
        assert printed["order"]["quantity"] == "0.005"
        assert printed["raw_quantity"] == "0.0051"

    def test_a_bad_number_is_reported_before_the_port_is_asked(
        self, app: Mock, submission: FakeOrderSubmission, capsys
    ) -> None:
        execute_order_preview(app, _args(qty="not-a-number"))

        assert submission.previewed == []
        assert "Invalid number" in capsys.readouterr().out


class TestOrderDryRun:
    def test_it_validates_the_same_order_it_previewed_and_never_submits(
        self, app: Mock, submission: FakeOrderSubmission, capsys
    ) -> None:
        """The guarantee that makes `order-dry-run` safe to run with trading
        off: it reaches the venue's test endpoint and nothing else."""
        execute_order_dry_run(app, _args())

        (previewed,) = submission.previewed
        (validated,) = submission.validated
        assert validated == previewed
        assert submission.submitted_live == []
        assert submission.submitted_dry == []
        assert "accepted" in capsys.readouterr().out.lower()

    def test_an_exchange_refusal_is_reported_not_raised(
        self, app: Mock, submission: FakeOrderSubmission, capsys
    ) -> None:
        submission.validate_raises(
            OrderRejectedByExchangeError(
                OrderRejectionReason.MIN_NOTIONAL, "Order's notional must be no smaller"
            )
        )

        execute_order_dry_run(app, _args())  # must not raise

        assert "min_notional" in capsys.readouterr().out.lower()

    def test_an_order_this_app_built_wrong_is_reported_not_raised(
        self, app: Mock, submission: FakeOrderSubmission, capsys
    ) -> None:
        """A different message from the one above, on purpose: the venue
        refusing an order and this app building an unroundable one are two
        different people's problems."""
        submission.validate_raises(
            InvalidOrderForSubmissionError("quantity 0.0051 is not aligned to 0.001")
        )

        execute_order_dry_run(app, _args())  # must not raise

        assert "not valid for submission" in capsys.readouterr().out
