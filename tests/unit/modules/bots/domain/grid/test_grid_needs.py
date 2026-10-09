"""`BOT-173` — what a ladder asks of the account, and the plan a resume proposes.

@details The numbers are the report's worked example (60,000–70,000, ten grids, 10,000
USDT at 65,000): ten levels, one left empty beside the price, five BUYs below and four
SELLs above. `resume_plan` is the sizing the executor proposes, so a screen that judges
a resume judges the ladder the resume would lay.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.ladder_needs import (
    resume_ladder_needs,
    start_ladder_needs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_needs import (
    resume_needs,
    start_needs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import plan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_resume_plan import (
    resume_plan,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)

from .report_example import CONFIG, LAST_PRICE, TERMS

_PARAMS = GridParams.from_config(CONFIG)
_PLAN = plan(_PARAMS, TERMS, LAST_PRICE)


def test_a_start_needs_the_opening_buy_and_the_buy_levels_in_quote_and_no_base() -> (
    None
):
    needs = start_needs(_PLAN, _PARAMS.capital_quote)

    opening = _PLAN.opening_buy_quantity * LAST_PRICE
    buys = sum((lv.price * lv.quantity for lv in _PLAN.buy_levels), Decimal(0))
    assert needs.quote == opening + buys
    assert needs.base == 0
    assert (needs.price, needs.capital) == (LAST_PRICE, Decimal(10000))


def test_what_a_start_needs_is_the_capital_less_the_level_left_empty() -> None:
    needs = start_needs(_PLAN, _PARAMS.capital_quote)

    assert needs.quote < _PARAMS.capital_quote
    assert needs.quote > _PARAMS.capital_quote * Decimal("0.8")


def test_a_resume_needs_the_sell_levels_base_and_the_buy_levels_quote() -> None:
    inventory = OwnerInventory(Decimal("0.5"), Decimal(30000))
    proposed = resume_plan(_PARAMS, TERMS, LAST_PRICE, inventory)

    needs = resume_needs(proposed, _PARAMS.capital_quote)

    assert needs.base == sum((lv.quantity for lv in proposed.sell_levels), Decimal(0))
    assert needs.base > 0
    assert needs.quote == sum(
        (lv.price * lv.quantity for lv in proposed.buy_levels), Decimal(0)
    )


def test_a_resume_sells_no_more_than_the_inventory_it_holds() -> None:
    held = Decimal("0.05")
    proposed = resume_plan(
        _PARAMS, TERMS, LAST_PRICE, OwnerInventory(held, Decimal(3000))
    )

    assert sum((lv.quantity for lv in proposed.sell_levels), Decimal(0)) <= held
    assert proposed.opening_buy_quantity == 0


def test_a_resume_buys_only_with_the_capital_the_inventory_leaves() -> None:
    cost = Decimal(9000)
    proposed = resume_plan(
        _PARAMS, TERMS, LAST_PRICE, OwnerInventory(Decimal("0.1"), cost)
    )

    spent = sum((lv.price * lv.quantity for lv in proposed.buy_levels), Decimal(0))
    assert spent <= _PARAMS.capital_quote - cost


def test_the_needs_of_unreadable_parameters_are_none_never_a_guess() -> None:
    broken = {**CONFIG, "grid_count": "not a number"}

    assert start_ladder_needs(broken, TERMS, LAST_PRICE) is None
    assert (
        resume_ladder_needs(
            broken, TERMS, LAST_PRICE, OwnerInventory(Decimal(1), Decimal(1))
        )
        is None
    )


def test_the_needs_from_parameters_are_the_needs_of_the_plan_they_draw() -> None:
    assert start_ladder_needs(CONFIG, TERMS, LAST_PRICE) == start_needs(
        _PLAN, _PARAMS.capital_quote
    )
