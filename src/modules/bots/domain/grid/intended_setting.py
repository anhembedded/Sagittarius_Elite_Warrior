"""`EPIC-039H` — the setting a Futures symbol will have once the bot starts.

@details The settings gate (`EPIC-039E`) makes a symbol's leverage and margin mode the grid's own at
Start, before the first order; a plan is therefore judged on that setting, not on the account's
current one. A symbol that sits on Cross, or at another leverage, is not a reason to refuse a plan
the gate will make right (and where the gate cannot, because a position or an order stands, Start
refuses in the gate's own words).

The screen's judgement (`evaluate_grid`) is this function's only caller: it *predicts* the setting
that Start's plan-time guard then reads back from the venue after the gate. The two are different
code, so the agreement is locked by a test that drives the real gate over the fake venue from a
Cross account and compares the verdicts (`test_plan_is_judged_on_the_intended_setting.py`).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_notional_cap import (
    allowed_notional,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBrackets,
)


def intended_setting(
    account: FuturesSymbolSetting, params: GridParams, brackets: LeverageBrackets
) -> FuturesSymbolSetting:
    """`account`'s symbol as the gate leaves it for `params`: isolated, at the grid's leverage,
    allowing what the brackets allow at that leverage (the account's own figure where no bracket
    allows it, which the plan's bracket check refuses by itself)."""
    return FuturesSymbolSetting(
        account.symbol,
        params.leverage,
        MarginType.ISOLATED,
        allowed_notional(brackets, params.leverage) or account.max_notional,
    )
