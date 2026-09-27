"""EPIC-027C — `ExchangeFilterPolicy`: floor to the step, refuse what the
exchange would refuse, and do nothing when no filters are known."""

import pytest
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.entry_rejection_reason import (
    EntryRejectionReason,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exchange_filters import (
    ExchangeFilters,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.policies.exchange_filter_policy import (
    ExchangeFilterPolicy,
)

_BTC_SPOT = ExchangeFilters(
    step_size=0.00001, min_quantity=0.00001, min_notional=5.0, tick_size=0.01
)


@pytest.mark.parametrize(
    ("raw", "floored"),
    [
        (0.123456789, 0.12345),
        (0.00001, 0.00001),
        (0.000019999, 0.00001),
        (0.000009999, 0.0),
        # Float edge values: `0.1 + 0.2` and `0.3` must land on the same step.
        (0.1 + 0.2, 0.3),
        (0.3, 0.3),
    ],
)
def test_floors_to_the_step_size(raw: float, floored: float):
    policy = ExchangeFilterPolicy(_BTC_SPOT)

    assert policy.floor_quantity(raw) == floored


def test_never_rounds_up():
    policy = ExchangeFilterPolicy(
        ExchangeFilters(
            step_size=0.001, min_quantity=0.0, min_notional=0.0, tick_size=0.1
        )
    )

    assert policy.floor_quantity(0.9999999) == 0.999


def test_a_quantity_below_the_minimum_quantity_is_rejected():
    policy = ExchangeFilterPolicy(
        ExchangeFilters(
            step_size=0.001, min_quantity=0.01, min_notional=0.0, tick_size=0.1
        )
    )

    assert policy.rejection_for(0.009, price=100_000.0) is (
        EntryRejectionReason.BELOW_MIN_QUANTITY
    )
    assert policy.rejection_for(0.01, price=100_000.0) is None


def test_a_zero_quantity_is_rejected_even_without_a_minimum_quantity():
    policy = ExchangeFilterPolicy(
        ExchangeFilters(
            step_size=0.001, min_quantity=0.0, min_notional=0.0, tick_size=0.1
        )
    )

    assert (
        policy.rejection_for(0.0, price=100.0)
        is EntryRejectionReason.BELOW_MIN_QUANTITY
    )


@pytest.mark.parametrize(
    ("quantity", "price", "rejection"),
    [
        (0.00004, 100_000.0, EntryRejectionReason.BELOW_MIN_NOTIONAL),  # 4.00
        (0.00005, 99_999.0, EntryRejectionReason.BELOW_MIN_NOTIONAL),  # 4.99995
        (0.00005, 100_000.0, None),  # exactly 5.00
        (0.00006, 100_000.0, None),  # 6.00
    ],
)
def test_the_minimum_notional_boundary(
    quantity: float, price: float, rejection: EntryRejectionReason | None
):
    assert ExchangeFilterPolicy(_BTC_SPOT).rejection_for(quantity, price) is rejection


def test_without_filters_nothing_is_floored_or_rejected():
    policy = ExchangeFilterPolicy(None)

    assert policy.floor_quantity(0.123456789) == 0.123456789
    assert policy.rejection_for(0.000000001, price=1.0) is None
