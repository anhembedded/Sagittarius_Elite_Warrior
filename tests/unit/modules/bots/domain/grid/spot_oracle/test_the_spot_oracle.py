"""`EPIC-039B` - a Long grid at leverage 1 is today's Spot grid, exactly.

`spot_oracle.json` holds what the planner and the simulator returned for 600 plans and 80
simulated walks **before** `039B` touched them (`record.py`). This test replays the same
inputs on the code as it is now and compares everything: every level's price, side and
quantity, the opening quantity, every fill, the equity curve, the profit split and the stop.
It is green on the day it was written and must stay green; a red here is Spot behaviour
moving, never an expectation to update.

Retire when: the Spot Grid is deleted, or the owner accepts a deliberate change to Spot
planning in a task of its own, which then records a new file beside this one.
"""

from __future__ import annotations

import json

import pytest
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.spot_oracle.corpus import (
    PLAN_CASES,
    SIMULATION_CASES,
    plan_cases,
    simulation_cases,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.spot_oracle.record import (
    ORACLE_FILE,
    plan_snapshot,
    simulation_snapshot,
)

_RECORDED = json.loads(ORACLE_FILE.read_text(encoding="utf-8"))


def test_the_recording_covers_the_whole_corpus() -> None:
    assert len(_RECORDED["plans"]) == PLAN_CASES
    assert len(_RECORDED["simulations"]) == SIMULATION_CASES


def test_the_recording_exercises_what_it_is_meant_to_prove() -> None:
    """Fills, completed cycles and every way a replay ends, or the oracle proves little."""
    simulations = _RECORDED["simulations"]
    assert sum(len(s["fills"]) for s in simulations) > 0
    assert sum(s["cycles"] for s in simulations) > 0
    assert {"end_of_data", "stop_loss", "take_profit", "halted"} <= {
        s["stop"] for s in simulations
    }


@pytest.mark.parametrize("index", range(PLAN_CASES))
def test_long_at_leverage_one_plans_as_the_recorded_spot_plan(index: int) -> None:
    assert plan_snapshot(plan_cases()[index]) == _RECORDED["plans"][index]


@pytest.mark.parametrize("index", range(SIMULATION_CASES))
def test_long_at_leverage_one_simulates_as_the_recorded_spot_result(
    index: int,
) -> None:
    assert (
        simulation_snapshot(simulation_cases()[index])
        == _RECORDED["simulations"][index]
    )
