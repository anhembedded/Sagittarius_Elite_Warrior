"""`EPIC-039K` — the costs and funding of a Futures replay, taken from `ICostModel`.

@details No fee or funding arithmetic is written here. The fees are `FuturesCostModel.fees()`
(the account's rates, as the terms carry them) and one settlement's charge is
`FuturesCostModel.funding_estimate` over one funding interval with the settlement's own rate,
which is position notional times rate: the model `EPIC-039G` shares between the planner's
checks, the readiness text and PnL. This module only assembles them into the value the pure
replay takes (`FuturesRunTerms`), because the replay lives in the domain and a cost model in
the application.

That `EPIC-039G`'s model names this very use as its extension case ("the backtest - an
implementation fed from recorded rates") and a recorded-rate implementation would need a
clock the port does not have: `funding_estimate(position, horizon)` carries no start time. So
the recorded rate is handed to the model one settlement at a time instead, and the port is
unchanged.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.positions.cost_model_futures import (
    FuturesCostModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    FUNDING_INTERVAL,
    ExchangeTerms,
    FundingView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_funding import (
    FundingCharger,
    FundingSchedule,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_run_terms import (
    FuturesRunTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBrackets,
)


def futures_run_terms(
    terms: ExchangeTerms, brackets: LeverageBrackets, funding: FundingSchedule
) -> FuturesRunTerms:
    """@return the terms a Futures replay runs under: the account's fees, the symbol's
    brackets, the funding settlements and how one is charged."""
    maker, taker = FuturesCostModel(terms, FundingView(None)).fees()
    return FuturesRunTerms(brackets, maker, taker, funding, _charger(terms))


def _charger(terms: ExchangeTerms) -> FundingCharger:
    def charge(position: Decimal, mark: Decimal, rate: Decimal) -> Decimal:
        model = FuturesCostModel(terms, FundingView(rate))
        estimate = model.funding_estimate(position * mark, FUNDING_INTERVAL)
        if estimate is None:
            raise ValueError("a recorded rate is a known rate")
        return estimate

    return charge
