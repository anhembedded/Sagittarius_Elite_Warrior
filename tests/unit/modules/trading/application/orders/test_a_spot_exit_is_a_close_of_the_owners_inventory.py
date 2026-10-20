"""`BUG-241` — which orders may be sent as a close on a venue without reduce-only.

@details Spot has no reduce-only, so a close there is judged by the owner's inventory instead
(`TradingLimitPolicy`). That is safe for one order only: a budgeted owner's SELL. A BUY, an
untagged order or a protective order on Spot would pass limits it must not, and stays refused
before it reaches the handler (`ExecuteOrderCommand`).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_purpose import (
    OrderPurpose,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .execute_order_builders import order_request

_TAG = "a3f9c1"
_SPOT = TradingVenue.SPOT_TESTNET
_PRICE = Decimal(64000)


def _close(**overrides: object) -> ExecuteOrderCommand:
    fields: dict[str, object] = {
        "side": OrderSide.SELL,
        "venue": _SPOT,
        "client_order_tag": _TAG,
    }
    request = order_request(**(fields | overrides))
    return ExecuteOrderCommand(
        order_request=request,
        live=True,
        purpose=overrides.get("purpose", OrderPurpose.CLOSE),  # type: ignore[arg-type]
    )


def test_a_budgeted_spot_sell_is_an_inventory_exit() -> None:
    assert _close().is_inventory_exit


def test_a_futures_reduce_only_close_is_not_an_inventory_exit() -> None:
    """It is exempt the Futures way, by the exchange's reduce-only flag."""
    request = order_request(
        side=OrderSide.SELL, reduce_only=True, client_order_tag=_TAG
    )

    command = ExecuteOrderCommand(
        order_request=request, live=True, purpose=OrderPurpose.CLOSE
    )

    assert not command.is_inventory_exit


@pytest.mark.parametrize(
    "overrides",
    [
        {"client_order_tag": None},
        {"side": OrderSide.BUY},
        {"order_type": OrderType.LIMIT, "reference_price": _PRICE},
    ],
    ids=["untagged", "buy", "resting-limit"],
)
def test_a_spot_close_that_is_not_a_budgeted_sell_is_refused_before_the_handler(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="reduce-only"):
        _close(**overrides)


def test_a_protective_order_on_spot_is_refused_even_when_tagged() -> None:
    request = order_request(side=OrderSide.SELL, venue=_SPOT, client_order_tag=_TAG)

    with pytest.raises(ValueError, match="reduce-only"):
        ExecuteOrderCommand(
            order_request=request, live=True, purpose=OrderPurpose.PROTECTIVE
        )


def test_a_tagged_spot_entry_is_not_an_exit() -> None:
    request = order_request(side=OrderSide.SELL, venue=_SPOT, client_order_tag=_TAG)

    command = ExecuteOrderCommand(order_request=request, live=True)

    assert not command.is_inventory_exit
