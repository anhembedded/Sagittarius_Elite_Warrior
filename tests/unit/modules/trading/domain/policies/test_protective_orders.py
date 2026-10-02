"""`EPIC-028I` — the take-profit and stop-loss that protect a filled entry
sit on the opposite side, are reduce-only and protective, and their prices
are checked against the entry's side."""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_purpose import (
    OrderPurpose,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.protective_levels import (
    ProtectiveLevels,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.protective_orders import (
    protection_problem,
    protective_orders_for,
)

_ENTRY = Decimal(60000)
_QTY = Decimal("0.02")


@pytest.mark.parametrize(
    ("entry_side", "exit_side", "tp", "sl"),
    [
        (OrderSide.BUY, OrderSide.SELL, Decimal(63000), Decimal(58000)),
        (OrderSide.SELL, OrderSide.BUY, Decimal(57000), Decimal(62000)),
    ],
    ids=["long", "short"],
)
def test_both_orders_close_on_the_opposite_side_and_only_reduce(
    entry_side: OrderSide, exit_side: OrderSide, tp: Decimal, sl: Decimal
) -> None:
    take_profit, stop_loss = protective_orders_for(
        "BTCUSDT", entry_side, _QTY, ProtectiveLevels(tp, sl), _ENTRY
    )

    assert (take_profit.order_type, take_profit.stop_price) == (
        OrderType.TAKE_PROFIT_MARKET,
        tp,
    )
    assert (stop_loss.order_type, stop_loss.stop_price) == (OrderType.STOP_MARKET, sl)
    for order in (take_profit, stop_loss):
        assert order.side is exit_side
        assert order.reduce_only is True
        assert order.purpose is OrderPurpose.PROTECTIVE
        assert (order.quantity, order.last_price) == (_QTY, _ENTRY)


def test_only_the_levels_named_are_placed() -> None:
    (only,) = protective_orders_for(
        "BTCUSDT", OrderSide.BUY, _QTY, ProtectiveLevels(None, Decimal(58000)), _ENTRY
    )

    assert only.order_type is OrderType.STOP_MARKET


def test_nothing_to_protect_is_refused() -> None:
    with pytest.raises(ValueError, match="quantity must be positive"):
        protective_orders_for(
            "BTCUSDT",
            OrderSide.BUY,
            Decimal(0),
            ProtectiveLevels(None, Decimal(1)),
            _ENTRY,
        )


def test_protection_with_no_level_is_no_protection() -> None:
    with pytest.raises(ValueError, match="take-profit, a stop-loss or both"):
        ProtectiveLevels(None, None)


@pytest.mark.parametrize(
    ("side", "tp", "sl", "problem"),
    [
        (OrderSide.BUY, Decimal(63000), Decimal(58000), None),
        (OrderSide.BUY, _ENTRY, None, "take-profit must be above"),
        (OrderSide.BUY, None, _ENTRY, "stop-loss must be below"),
        (OrderSide.SELL, Decimal(57000), Decimal(62000), None),
        (OrderSide.SELL, Decimal(61000), None, "take-profit must be below"),
        (OrderSide.SELL, None, Decimal(59000), "stop-loss must be above"),
    ],
)
def test_each_level_must_sit_on_its_side_of_the_entry(
    side: OrderSide, tp: Decimal | None, sl: Decimal | None, problem: str | None
) -> None:
    found = protection_problem(side, _ENTRY, ProtectiveLevels(tp, sl))

    assert (found is None) if problem is None else (problem in (found or ""))
