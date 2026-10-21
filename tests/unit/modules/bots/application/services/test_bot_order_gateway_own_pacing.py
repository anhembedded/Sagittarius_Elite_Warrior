"""`BUG-254` - the owner budget's own pacing is "not yet" for a bot, never a refusal that halts it.

@details Trading refuses an order stamped sooner than the budget's spacing after the previous one,
and one more than the budget's rate inside its window. Both are the app's speed limits, not a
verdict on the order or the venue. The gateway takes another turn and sends a too-soon order
again, and answers a rate refusal, or a spacing that kept missing, as a pause (`RATE_LIMITED`) the
bot waits out and resumes from; read as `REFUSED`, a start halted and sold its position at market.
The journey against the real policy is `test_a_burst_of_orders_is_not_refused_by_the_budgets_spacing_on_the_fake_exchange.py`.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_order_gateway import (
    BotIdentity,
    BotOrderGateway,
    OrderOutcomeKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.order_outcome import (
    OrderOutcome,
    opening_outcome,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.paced_send import (
    PACING_RETRIES,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudget,
    OwnerBudgetFacts,
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    TradingLimitContext,
    TradingLimitViolation,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world_doubles import (
    CountingPacer,
)

D = Decimal
V = TradingLimitViolation

_BUDGET = OwnerBudget(
    max_open_orders=150,
    max_exposure_quote=D(1000),
    min_order_spacing=timedelta(milliseconds=250),
    max_orders_per_window=60,
    window=timedelta(minutes=1),
)


def _blocked(violation: V, since_last: timedelta | None) -> ExecuteOrderResult:
    facts = OwnerBudgetFacts(
        budget=_BUDGET,
        open_order_count=0,
        open_buy_quote=D(0),
        open_sell_quantity=D(0),
        inventory=OwnerInventory(D(0), D(0)),
        time_since_last_order=since_last,
        orders_in_window=0,
        order_side=OrderSide.BUY,
        order_quantity=D("0.01"),
    )
    context = TradingLimitContext(
        orders_sent_this_session=0,
        order_notional=D(10),
        open_position_count_for_symbol=0,
        time_since_last_order_for_symbol=None,
        client_order_tag="abc123",
        owner_budget=facts,
    )
    return ExecuteOrderResult(violation, None, (), None, context)


def _too_soon() -> ExecuteOrderResult:
    return _blocked(V.OWNER_BUDGET_SPACING, timedelta(milliseconds=220))


def _sent() -> ExecuteOrderResult:
    order = Mock()
    order.client_order_id = "SEW-abc123-1"
    order.quantity = D("0.01")
    return ExecuteOrderResult(None, None, (), order)


def _gateway(
    *answers: ExecuteOrderResult,
) -> tuple[BotOrderGateway, CountingPacer, Mock]:
    pacer = CountingPacer()
    ports = Mock()
    ports.order_submission.submit.side_effect = list(answers)
    gateway = BotOrderGateway(
        ports, BotIdentity("bot.abc123", "abc123", "BNBUSDT"), pacer
    )
    return gateway, pacer, ports.order_submission.submit


def test_an_order_found_too_soon_takes_another_turn_and_is_sent_again() -> None:
    gateway, pacer, submit = _gateway(_too_soon(), _sent())

    outcome = gateway.place_limit(OrderSide.BUY, D(740), D("0.01"))

    assert outcome.kind is OrderOutcomeKind.DONE
    assert pacer.turns == 2
    assert submit.call_count == 2


def test_turns_that_keep_missing_pause_the_bot_by_what_trading_found_missing() -> None:
    gateway, pacer, submit = _gateway(*[_too_soon()] * (PACING_RETRIES + 1))

    outcome = gateway.place_limit(OrderSide.BUY, D(740), D("0.01"))

    assert outcome.kind is OrderOutcomeKind.RATE_LIMITED
    assert outcome.retry_after == timedelta(milliseconds=30)
    assert pacer.turns == submit.call_count == PACING_RETRIES + 1
    assert gateway.take_rate_limit() == timedelta(milliseconds=30), (
        "the halt schedules its resume by the pause"
    )


def test_a_rate_refusal_pauses_the_bot_for_the_budgets_window_and_is_not_retried() -> (
    None
):
    gateway, pacer, submit = _gateway(_blocked(V.OWNER_BUDGET_RATE, None))

    outcome = gateway.place_limit(OrderSide.BUY, D(740), D("0.01"))

    assert outcome.kind is OrderOutcomeKind.RATE_LIMITED
    assert outcome.retry_after == _BUDGET.window
    assert pacer.turns == submit.call_count == 1
    assert gateway.take_rate_limit() == _BUDGET.window


@pytest.mark.parametrize(
    "violation",
    [V.OWNER_BUDGET_OPEN_ORDERS, V.OWNER_BUDGET_MARGIN, V.OWNER_BUDGET_MISSING],
)
def test_a_refusal_that_is_not_pacing_still_halts_the_bot(violation: V) -> None:
    gateway, pacer, submit = _gateway(_blocked(violation, None))

    outcome = gateway.place_limit(OrderSide.BUY, D(740), D("0.01"))

    assert outcome.kind is OrderOutcomeKind.REFUSED
    assert outcome.detail == violation.value
    assert pacer.turns == submit.call_count == 1


@pytest.mark.parametrize(
    ("slice_number", "kind"),
    [(1, OrderOutcomeKind.RATE_LIMITED), (2, OrderOutcomeKind.REFUSED)],
)
def test_an_own_budget_pause_after_an_opening_slice_filled_stays_a_refusal(
    slice_number: int, kind: OrderOutcomeKind
) -> None:
    paused = OrderOutcome(
        OrderOutcomeKind.RATE_LIMITED,
        "id",
        "own budget",
        timedelta(seconds=1),
        own_budget=True,
    )

    assert opening_outcome(slice_number, paused).kind is kind


def test_an_exchange_pause_is_a_pause_in_every_opening_slice() -> None:
    exchange = OrderOutcome(
        OrderOutcomeKind.RATE_LIMITED, "id", "429", timedelta(seconds=30)
    )

    assert opening_outcome(2, exchange) is exchange
