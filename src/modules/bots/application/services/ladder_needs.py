"""`BOT-174` — what a bot's plan asks of the account, from its parameters and the market.

@details The readiness rules (`exchange_rules.py`) compare these numbers with the
exchange's facts. They are the plan the executors would draw at that price
(`plan`, `resume_plan`), reduced by `grid_needs`, so the screen, the Start use
case and the Resume use case judge one plan.

A Grid is the only kind today: a second kind adds its own function here, chosen by
the kind id, and the rules stay as they are. `None` means no plan can be drawn
(the parameters do not parse); the Design step names that, and a rule that needs
the plan then says nothing.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_needs import (
    LadderNeeds,
    resume_needs,
    start_needs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
    GridParamsError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import plan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_resume_plan import (
    resume_plan,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)


def start_ladder_needs(
    config: Mapping[str, str], terms: ExchangeTerms, price: Decimal
) -> LadderNeeds | None:
    params = _params(config)
    if params is None:
        return None
    return start_needs(plan(params, terms, price), params.capital_quote)


def resume_ladder_needs(
    config: Mapping[str, str],
    terms: ExchangeTerms,
    price: Decimal,
    inventory: OwnerInventory,
) -> LadderNeeds | None:
    params = _params(config)
    if params is None:
        return None
    return resume_needs(
        resume_plan(params, terms, price, inventory), params.capital_quote
    )


def _params(config: Mapping[str, str]) -> GridParams | None:
    try:
        return GridParams.from_config(config)
    except GridParamsError:
        return None
