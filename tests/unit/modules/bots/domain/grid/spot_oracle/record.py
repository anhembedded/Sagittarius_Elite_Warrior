"""`EPIC-039B` - what the Spot planner and simulator return, in a form a JSON file keeps.

`snapshot_plan` and `snapshot_simulation` are the only readers of a plan and a result the
oracle uses. `python -m ...record` wrote `spot_oracle.json` from the code **before** `039B`;
it is never run again to make a failing test pass (the file is the evidence, not an output).
"""

from __future__ import annotations

import json
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    GridBacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    GridPlan,
    plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_simulator import (
    GridBacktestInputs,
    simulate_grid,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.spot_oracle.corpus import (
    MINUTE,
    PlanCase,
    SimulationCase,
    plan_cases,
    simulation_cases,
)

ORACLE_FILE = Path(__file__).with_name("spot_oracle.json")


def snapshot_of_plan(grid_plan: GridPlan) -> dict[str, object]:
    return {
        "capital_per_level": str(grid_plan.capital_per_level),
        "opening": str(grid_plan.opening_buy_quantity),
        "levels": [
            [level.index, str(level.price), level.side.value, str(level.quantity)]
            for level in grid_plan.levels
        ],
    }


def plan_snapshot(case: PlanCase) -> dict[str, object]:
    return snapshot_of_plan(
        plan(GridParams.from_config(case.config), case.terms, case.last_price)
    )


def snapshot_of_result(result: GridBacktestResult) -> dict[str, object]:
    return {
        "plan": snapshot_of_plan(result.plan),
        "stop": result.stop_reason.value,
        "grid_profit": str(result.grid_profit),
        "unrealised": str(result.unrealised),
        "cycles": result.completed_cycles,
        "maker_fees": str(result.maker_fees),
        "taker_fees": str(result.taker_fees),
        "average_cost": None
        if result.average_cost is None
        else str(result.average_cost),
        "fills": [
            [
                fill.time.isoformat(),
                fill.side.value,
                str(fill.price),
                str(fill.quantity),
                str(fill.fee_quote),
                fill.level_index,
                fill.maker,
            ]
            for fill in result.fills
        ],
        "equity": [
            [point.time.isoformat(), str(point.grid), str(point.buy_and_hold)]
            for point in result.equity
        ],
    }


def simulation_snapshot(case: SimulationCase) -> dict[str, object]:
    result = simulate_grid(
        GridBacktestInputs(
            GridParams.from_config(case.config), case.terms, case.bars, MINUTE
        )
    )
    assert isinstance(result, GridBacktestResult)
    return snapshot_of_result(result)


def record() -> None:
    document = {
        "plans": [plan_snapshot(case) for case in plan_cases()],
        "simulations": [simulation_snapshot(case) for case in simulation_cases()],
    }
    ORACLE_FILE.write_text(
        json.dumps(document, separators=(",", ":")) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    record()
