"""`EPIC-034H` — two facts the Run step reads before the click: which other bot
holds the exchange (ADR D20), and whether the owner budget fits trading's caps."""

from __future__ import annotations

from dataclasses import replace

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_budget import (
    grid_budget_problem,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.other_active_bot import (
    other_active_bot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RUN_STARTING_STATES,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    DEFAULT_OWNER_BUDGET_CAPS,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    CONFIG,
)

S = BotLifecycleState
_ACTIVE = [s for s in S if s not in RUN_STARTING_STATES]


@pytest.mark.parametrize("state", _ACTIVE)
def test_every_state_a_new_run_does_not_start_from_is_active(state: S) -> None:
    assert other_active_bot("b", [("a", state), ("b", S.DRAFT)]) == "a"


@pytest.mark.parametrize("state", sorted(RUN_STARTING_STATES, key=lambda s: s.value))
def test_a_bot_at_rest_is_not_active(state: S) -> None:
    assert other_active_bot("b", [("a", state)]) == ""


def test_the_bot_itself_is_never_another_bot() -> None:
    assert other_active_bot("a", [("a", S.RUNNING)]) == ""


def test_a_refused_file_is_active_unless_it_is_the_bots_own() -> None:
    assert other_active_bot("b", [], ["a.json"]) == "a.json"
    assert other_active_bot("b", [], ["b.json"]) == ""


def test_a_ladder_within_the_caps_has_no_budget_problem() -> None:
    assert grid_budget_problem(CONFIG, DEFAULT_OWNER_BUDGET_CAPS) == ""


def test_a_ladder_one_order_past_the_cap_names_both_numbers() -> None:
    """Four grids keep five orders open; a cap of four refuses it."""
    caps = replace(DEFAULT_OWNER_BUDGET_CAPS, max_open_orders=4)

    problem = grid_budget_problem(CONFIG, caps)

    assert "5 orders" in problem
    assert "at most 4" in problem


def test_a_ladder_exactly_at_the_cap_passes() -> None:
    caps = replace(DEFAULT_OWNER_BUDGET_CAPS, max_open_orders=5)

    assert grid_budget_problem(CONFIG, caps) == ""


def test_parameters_that_cannot_be_read_are_the_design_steps_to_say() -> None:
    assert grid_budget_problem({"lower": "x"}, DEFAULT_OWNER_BUDGET_CAPS) == ""
