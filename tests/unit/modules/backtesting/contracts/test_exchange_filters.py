"""EPIC-027C — `ExchangeFilters` refuses values no exchange publishes."""

import pytest
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exchange_filters import (
    ExchangeFilters,
)


def test_accepts_real_spot_btcusdt_filters():
    filters = ExchangeFilters(
        step_size=0.00001, min_quantity=0.00001, min_notional=5.0, tick_size=0.01
    )

    assert filters.step_size == 0.00001


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("step_size", 0.0, "step_size"),
        ("tick_size", 0.0, "tick_size"),
        ("min_quantity", -0.1, "min_quantity"),
        ("min_notional", -1.0, "min_notional"),
    ],
)
def test_refuses_an_impossible_value(field: str, value: float, message: str):
    values = {
        "step_size": 0.001,
        "min_quantity": 0.001,
        "min_notional": 5.0,
        "tick_size": 0.1,
        field: value,
    }

    with pytest.raises(ValueError, match=message):
        ExchangeFilters(**values)


def test_zero_minimums_are_allowed():
    filters = ExchangeFilters(
        step_size=1.0, min_quantity=0.0, min_notional=0.0, tick_size=1.0
    )

    assert filters.min_notional == 0.0
