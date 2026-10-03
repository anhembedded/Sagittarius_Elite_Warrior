"""`EPIC-029` ADR D6 — `ExecuteOrderCommandHandler` judges a tagged order by
its owner's budget, and records it in the owner's book.

@details The handler, its session state and its policy are real; the book
is installed the way `RegisterOwnerBudgetCommandHandler` installs it. The
signal limits are the defaults (one position per symbol, 60 s between
orders), which would refuse the second order outright.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.command import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_book import (
    OwnerBook,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    EMPTY_INVENTORY,
    OwnerBudget,
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistration,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    TradingLimitViolation,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.orders.execute_order_builders import (
    make_handler,
    order_request,
)

_TAG = "a3f9c1"
_OWNER = "bot-1"


def _registration(spacing: timedelta = timedelta(0)) -> OwnerBudgetRegistration:
    return OwnerBudgetRegistration(
        owner_id=_OWNER,
        tag=_TAG,
        symbol="BTCUSDT",
        run_started_at=datetime(2026, 10, 1, tzinfo=UTC),
        budget=OwnerBudget(
            max_open_orders=10,
            max_exposure_quote=Decimal(5000),
            min_order_spacing=spacing,
            max_orders_per_window=60,
            window=timedelta(minutes=1),
        ),
    )


def _budgeted(
    inventory: OwnerInventory = EMPTY_INVENTORY, spacing: timedelta = timedelta(0)
) -> tuple[object, TradingSessionState, Mock]:
    raw_client = Mock()
    raw_client.futures_create_order.return_value = {}
    handler, state = make_handler(raw_client=raw_client)
    state.install_owner_book(
        _TAG,
        OwnerBook(_registration(spacing), inventory),
        expected_switch_epoch=state.switch_epoch,
    )
    return handler, state, raw_client


def _ladder_order(side: OrderSide = OrderSide.BUY, price: int = 60000, **extra: object):
    return ExecuteOrderCommand(
        order_request=order_request(
            order_type=OrderType.LIMIT,
            side=side,
            reference_price=Decimal(price),
            client_order_tag=_TAG,
            **extra,
        ),
        live=True,
        owner_id=_OWNER,
    )


def test_ten_resting_orders_pass_and_the_eleventh_is_refused() -> None:
    """The signal limits would have refused the second; the budget allows
    ten and refuses the eleventh."""
    handler, _, raw_client = _budgeted()

    results = [handler.execute(_ladder_order(price=60000 - 10 * n)) for n in range(11)]

    assert [r.blocked_by for r in results[:10]] == [None] * 10
    assert results[10].blocked_by is TradingLimitViolation.OWNER_BUDGET_OPEN_ORDERS
    assert raw_client.futures_create_order.call_count == 10


def test_a_budgeted_order_leaves_the_signal_bookkeeping_alone() -> None:
    """It neither marks the symbol open nor counts against the session's
    orders, so a manual order elsewhere is judged as before."""
    handler, state, _ = _budgeted()

    handler.execute(_ladder_order())

    assert state.orders_sent_this_session == 0
    assert state.open_position_count("BTCUSDT") == 0


def test_a_sell_beyond_the_owners_inventory_is_refused() -> None:
    handler, _, raw_client = _budgeted(OwnerInventory(Decimal("0.001"), Decimal(60)))

    result = handler.execute(_ladder_order(OrderSide.SELL, 61000))

    assert (
        result.blocked_by is TradingLimitViolation.OWNER_BUDGET_SELL_EXCEEDS_INVENTORY
    )
    raw_client.futures_create_order.assert_not_called()


def test_an_order_closer_than_the_spacing_is_refused() -> None:
    handler, _, _ = _budgeted(spacing=timedelta(minutes=5))

    first = handler.execute(_ladder_order())
    second = handler.execute(_ladder_order(price=59990))

    assert first.blocked_by is None
    assert second.blocked_by is TradingLimitViolation.OWNER_BUDGET_SPACING


def test_a_tagged_order_without_a_budget_is_refused() -> None:
    raw_client = Mock()
    handler, _ = make_handler(raw_client=raw_client)

    result = handler.execute(_ladder_order())

    assert result.blocked_by is TradingLimitViolation.OWNER_BUDGET_MISSING
    raw_client.futures_create_order.assert_not_called()


def test_a_tag_held_by_another_owner_counts_as_no_budget() -> None:
    handler, _, _ = _budgeted()
    command = _ladder_order()
    impostor = ExecuteOrderCommand(
        order_request=command.order_request, live=True, owner_id="bot-2"
    )

    assert handler.execute(impostor).blocked_by is (
        TradingLimitViolation.OWNER_BUDGET_MISSING
    )


def test_a_disable_clears_the_budget_so_the_next_tagged_order_is_refused() -> None:
    handler, state, _ = _budgeted()

    state.disable()
    state.enable(set())

    assert handler.execute(_ladder_order()).blocked_by is (
        TradingLimitViolation.OWNER_BUDGET_MISSING
    )
