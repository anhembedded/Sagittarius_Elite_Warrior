"""`EPIC-029` ADR O1 — the global caps on what an owner budget may declare."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    DEFAULT_OWNER_BUDGET_CAPS,
    OwnerBudget,
)

_AT_THE_CAPS = OwnerBudget(
    max_open_orders=100,
    max_exposure_quote=Decimal(5000),
    min_order_spacing=timedelta(milliseconds=250),
    max_orders_per_window=60,
    window=timedelta(minutes=1),
)


def test_a_budget_at_every_cap_fits() -> None:
    assert DEFAULT_OWNER_BUDGET_CAPS.exceeded_by(_AT_THE_CAPS) is None


@pytest.mark.parametrize(
    ("change", "cap"),
    [
        ({"max_open_orders": 101}, "max_open_orders"),
        ({"min_order_spacing": timedelta(milliseconds=249)}, "min_order_spacing"),
        ({"max_orders_per_window": 61}, "max_orders_per_minute"),
        (
            {"max_orders_per_window": 2, "window": timedelta(seconds=1)},
            "max_orders_per_minute",
        ),
    ],
)
def test_a_budget_past_a_cap_names_it(change: dict[str, object], cap: str) -> None:
    budget = replace(_AT_THE_CAPS, **change)  # type: ignore[arg-type]
    assert DEFAULT_OWNER_BUDGET_CAPS.exceeded_by(budget) == cap


def test_the_rate_is_compared_not_the_raw_count() -> None:
    """120 orders per two minutes is the approved 60 per minute."""
    budget = replace(
        _AT_THE_CAPS, max_orders_per_window=120, window=timedelta(minutes=2)
    )
    assert DEFAULT_OWNER_BUDGET_CAPS.exceeded_by(budget) is None


@pytest.mark.parametrize(
    "change",
    [
        {"max_open_orders": 0},
        {"max_orders_per_window": 0},
        {"max_exposure_quote": Decimal(0)},
        {"window": timedelta(0)},
    ],
)
def test_a_budget_that_allows_nothing_cannot_be_built(
    change: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="owner budget"):
        replace(_AT_THE_CAPS, **change)  # type: ignore[arg-type]
