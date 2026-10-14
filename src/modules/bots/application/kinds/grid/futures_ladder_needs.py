"""`EPIC-039H` — what a Futures ladder asks of the account: margin, from the plan alone.

@details The Futures counterpart of `ladder_needs.py`. The readiness rules (`futures_rules.py`)
compare these numbers with the exchange's facts: the notional of the largest position the ladder
can reach (`worst_case_positions`, `EPIC-039F`), the initial margin it reserves at the leverage the
bot asked for, and that leverage. They are pure functions of the plan the executor would draw
(`plan` with the venue's equal-quantity sizing), so the screen, the Start use case and the
executor judge one plan.

  · **A start** opens its position at market and then lays the ladder: the worst case is the far
    edge of the range (LONG: every BUY filled on top of the opening).
  · **A resume** lays no opening: the held position is the bot's, the BUY levels add to it.

`None` means no plan can be drawn (the parameters do not parse); the Design step names that.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_needs import (
    FuturesNeeds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_worst_case import (
    worst_case_positions,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
    GridParamsError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    LevelSizing,
    plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_resume_plan import (
    resume_plan,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)


def start_futures_needs(
    config: Mapping[str, str], terms: ExchangeTerms, price: Decimal
) -> FuturesNeeds | None:
    params = _params(config)
    if params is None:
        return None
    ladder = plan(params, terms, price, LevelSizing.EQUAL_QUANTITY)
    notional = max(
        (p.notional for p in worst_case_positions(ladder)), default=Decimal(0)
    )
    return FuturesNeeds(notional / params.leverage, notional, params.leverage)


def resume_futures_needs(
    config: Mapping[str, str],
    terms: ExchangeTerms,
    price: Decimal,
    inventory: OwnerInventory,
) -> FuturesNeeds | None:
    params = _params(config)
    if params is None:
        return None
    ladder = resume_plan(params, terms, price, inventory, LevelSizing.EQUAL_QUANTITY)
    notional = inventory.cost + sum(
        (level.notional for level in ladder.buy_levels), Decimal(0)
    )
    return FuturesNeeds(notional / params.leverage, notional, params.leverage)


def _params(config: Mapping[str, str]) -> GridParams | None:
    try:
        return GridParams.from_config(config)
    except GridParamsError:
        return None
