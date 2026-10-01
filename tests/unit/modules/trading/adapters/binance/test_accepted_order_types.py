"""`EPIC-028O` — what a venue's client factory says it can send is exactly
what its payload mapper sends.

@details `ExecuteOrderCommandHandler` refuses an order type by name, before
any request, from `ITradingClientFactory.accepted_order_types()` (the PR #302
review, should-fix 1). If the factory claimed a type the mapper refuses, the
refusal would come back as an exception from inside `place_order` again; if
it omitted one the mapper sends, a working order would be refused. Each
order type is built with every field any type needs, so only the type can
make the mapper refuse it.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_order_payload_mapper import (
    map_order_to_futures_params,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client_factory import (
    FuturesTradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_order_payload_mapper import (
    map_order_to_spot_params,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_trading_client_factory import (
    SpotTradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client_factory import (
    ITradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.invalid_order_for_submission import (
    InvalidOrderForSubmissionError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.time_in_force import (
    TimeInForce,
)

_METADATA = SymbolOrderMetadata(
    symbol="BTCUSDT",
    status="TRADING",
    step_size=Decimal("0.001"),
    tick_size=Decimal("0.01"),
    min_notional=Decimal(5),
    quantity_precision=3,
    price_precision=2,
    fetched_at=datetime(2026, 10, 1, tzinfo=UTC),
)

type Mapper = Callable[[Order, SymbolOrderMetadata], dict[str, Any]]

_VENUES: list[tuple[str, ITradingClientFactory, Mapper]] = [
    (
        "futures",
        FuturesTradingClientFactory(Mock(), Mock(), Mock()),
        map_order_to_futures_params,
    ),
    (
        "spot",
        SpotTradingClientFactory(Mock(), Mock(), Mock()),
        map_order_to_spot_params,
    ),
]


def _complete_order(order_type: OrderType) -> Order:
    return Order(
        client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=order_type,
        quantity=Decimal("0.002"),
        price=Decimal("64100.00"),
        stop_price=Decimal("64050.00"),
        time_in_force=TimeInForce.GTC,
    )


def _sends(mapper: Mapper, order_type: OrderType) -> bool:
    try:
        mapper(_complete_order(order_type), _METADATA)
    except InvalidOrderForSubmissionError:
        return False
    return True


@pytest.mark.parametrize(
    ("venue", "factory", "mapper"), _VENUES, ids=[v[0] for v in _VENUES]
)
@pytest.mark.parametrize(
    "order_type",
    list(OrderType),
    ids=lambda t: t.name,
)
def test_the_factory_accepts_a_type_exactly_when_the_mapper_sends_it(
    venue: str, factory: ITradingClientFactory, mapper: Mapper, order_type: OrderType
) -> None:
    assert (order_type in factory.accepted_order_types()) is _sends(mapper, order_type)
