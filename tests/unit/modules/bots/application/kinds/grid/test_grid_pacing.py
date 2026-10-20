"""`BUG-238` — the pace a Grid's orders keep is the pace its budget asks trading for.

Trading refuses an order past the budget's rate (`owner_budget_rate`); a bot paced at any other
figure meets that refusal. The pacing is therefore read off the budget, not configured twice, and
the Design step judges a ladder by what it keeps open, not by how many orders a minute it needs:
the pacer lays a ladder longer than the rate over more than a minute.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_budget import (
    grid_budget,
    grid_budget_problem,
    grid_pacing,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_order_pacer import (
    OrderPacing,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    DEFAULT_OWNER_BUDGET_CAPS,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    CONFIG,
)

#: More levels than the 60 orders a minute the default caps allow, fewer than the 150 open orders.
LEVELS_PAST_THE_RATE = 70


def test_the_pacing_is_the_spacing_and_the_rate_the_budget_declares() -> None:
    caps = replace(
        DEFAULT_OWNER_BUDGET_CAPS,
        min_order_spacing=timedelta(milliseconds=400),
        max_orders_per_minute=42,
    )

    pacing = grid_pacing(grid_budget(GridParams.from_config(CONFIG), caps))

    assert pacing == OrderPacing(timedelta(milliseconds=400), 42, timedelta(minutes=1))


def test_a_ladder_longer_than_the_rate_has_no_design_problem_because_it_is_paced() -> (
    None
):
    config = {**CONFIG, "grid_count": str(LEVELS_PAST_THE_RATE)}

    assert grid_budget_problem(config, DEFAULT_OWNER_BUDGET_CAPS) == ""


def test_a_ladder_that_could_never_fit_the_open_order_cap_is_still_refused() -> None:
    cap = DEFAULT_OWNER_BUDGET_CAPS.max_open_orders
    config = {**CONFIG, "grid_count": str(cap)}

    problem = grid_budget_problem(config, DEFAULT_OWNER_BUDGET_CAPS)

    assert f"{cap + 1} orders" in problem
    assert f"at most {cap}" in problem


def test_a_ladder_of_140_levels_passes_the_design_check_and_160_is_refused() -> None:
    fits = {**CONFIG, "grid_count": "139"}
    too_long = {**CONFIG, "grid_count": "159"}

    assert grid_budget_problem(fits, DEFAULT_OWNER_BUDGET_CAPS) == ""
    problem = grid_budget_problem(too_long, DEFAULT_OWNER_BUDGET_CAPS)
    assert "160 orders" in problem
    assert "at most 150" in problem
