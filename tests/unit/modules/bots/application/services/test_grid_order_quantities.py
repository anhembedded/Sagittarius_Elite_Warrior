"""`BUG-205` — `adopt_exchange_quantities`: a saved order takes the exchange's quantity."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.recovery.grid_order_quantities import (
    QuantityExceedsSaved,
    adopt_exchange_quantities,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_level_fsm_matrix import (
    LevelState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
    LevelOrder,
    RuntimeLevel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType

_ID = "SEW-ke95g7-fb52e1da7a"


def _runtime(saved: str = "0.0022") -> GridRuntime:
    order = LevelOrder(_ID, OrderSide.SELL, Decimal(2667), Decimal(saved))
    level = RuntimeLevel(6, Decimal(2667), Decimal("0.0022"), LevelState.RESTING, order)
    return GridRuntime((level,))


def _listed(quantity: str) -> Order:
    return Order(
        ClientOrderId(_ID),
        "ETHUSDT",
        OrderSide.SELL,
        OrderType.LIMIT,
        Decimal(quantity),
        price=Decimal(2667),
    )


def _record(quantity: str) -> OrderRecord:
    return OrderRecord(
        _listed(quantity),
        Decimal(quantity),
        Decimal(2667),
        datetime(2026, 10, 14, tzinfo=UTC),
        1,
    )


def _quantity(runtime: GridRuntime | QuantityExceedsSaved) -> Decimal:
    assert isinstance(runtime, GridRuntime)
    return runtime.levels[0].order.quantity  # type: ignore[union-attr]


def test_a_smaller_quantity_listed_open_is_adopted() -> None:
    assert _quantity(
        adopt_exchange_quantities("b", _runtime(), (_listed("0.0021"),), {})
    ) == Decimal("0.0021")


def test_a_smaller_quantity_from_history_is_adopted_for_an_order_no_longer_open() -> (
    None
):
    assert _quantity(
        adopt_exchange_quantities("b", _runtime(), (), {_ID: _record("0.0021")})
    ) == Decimal("0.0021")


def test_the_open_list_wins_over_history() -> None:
    adopted = adopt_exchange_quantities(
        "b", _runtime(), (_listed("0.0021"),), {_ID: _record("0.0020")}
    )

    assert _quantity(adopted) == Decimal("0.0021")


def test_an_equal_quantity_or_an_unknown_order_changes_nothing() -> None:
    runtime = _runtime()

    assert adopt_exchange_quantities("b", runtime, (_listed("0.0022"),), {}) == runtime
    assert adopt_exchange_quantities("b", runtime, (), {}) == runtime


def test_a_larger_quantity_is_refused_not_adopted() -> None:
    outcome = adopt_exchange_quantities("b", _runtime(), (_listed("0.0023"),), {})

    assert outcome == QuantityExceedsSaved(_ID, 6, Decimal("0.0022"), Decimal("0.0023"))
    assert "0.0023" in outcome.detail and "0.0022" in outcome.detail
