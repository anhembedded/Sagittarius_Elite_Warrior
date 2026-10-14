"""`EPIC-029E` — the owner budget a Grid asks trading for (ADR D6, §3.2, O1).

  · `max_open_orders = grid_count + 1`, the number of levels: an upper bound
    with one level of slack;
  · `max_exposure_quote = capital_quote`;
  · the spacing and the rate are the global caps trading is configured with
    (`OwnerBudgetCaps`, ADR O1): the bot asks for as fast as it is allowed, and
    trading refuses anything faster.

The bot never supplies its inventory: trading derives it from the venue's
history of the bot's tagged orders since `run_started_at` (D6). The bot asks
again — which re-derives it — before any order in any state: reconciliation, a
resume from HALTED, a STOPPING retry, and ERROR → `stop`.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
    GridParamsError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudget,
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistration,
)

_ONE_MINUTE = timedelta(minutes=1)


def bot_owner_id(bot_id: str) -> str:
    """The owner a bot is to trading: its lease and its budget (`bot.<id>`),
    the same name its chart's stream is held under (`bot_stream_owner`)."""
    return f"bot.{bot_id}"


def grid_budget(params: GridParams, caps: OwnerBudgetCaps) -> OwnerBudget:
    return OwnerBudget(
        max_open_orders=params.grid_count + 1,
        max_exposure_quote=params.capital_quote,
        min_order_spacing=caps.min_order_spacing,
        max_orders_per_window=caps.max_orders_per_minute,
        window=_ONE_MINUTE,
    )


def grid_registration(
    bot_id: str,
    symbol: str,
    run_started_at: datetime,
    budget: OwnerBudget,
) -> OwnerBudgetRegistration:
    """The registration for one run of one bot; the tag is the bot's id (D5)."""
    return OwnerBudgetRegistration(
        owner_id=bot_owner_id(bot_id),
        tag=bot_id,
        symbol=symbol,
        run_started_at=run_started_at,
        budget=budget,
    )


def grid_budget_problem(config: Mapping[str, str], caps: OwnerBudgetCaps) -> str:
    """Which cap a Grid's budget would exceed, in words; `""` when it fits or
    the parameters cannot be read (the Design step says so, `EPIC-034H`).

    Trading refuses the same budget at registration; asking here lets the
    screen say so before the click, in the same cap's name.
    """
    try:
        params = GridParams.from_config(config)
    except GridParamsError:
        return ""
    exceeded = caps.exceeded_by(grid_budget(params, caps))
    if exceeded is None:
        return ""
    if exceeded == "max_open_orders":
        return (
            f"The ladder keeps {params.grid_count + 1} orders open; trading allows "
            f"at most {caps.max_open_orders}. Use fewer grids"
        )
    return f"The bot's order budget exceeds trading's cap ({exceeded})"
