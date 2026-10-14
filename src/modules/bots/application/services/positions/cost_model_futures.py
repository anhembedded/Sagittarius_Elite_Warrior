"""`EPIC-039G` — Futures' `ICostModel`: the account's rates (quote asset) plus funding."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_cost_model import ICostModel
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    FUNDING_INTERVAL,
    ExchangeTerms,
    FundingView,
)


class FuturesCostModel(ICostModel):
    """The fees come from the account (`FuturesCommissionRateReader`, through the terms),
    never from a constant: tiers and discounts change them. The funding rate is the one the
    exchange reported when the model was built, applied at the same rate for the whole
    horizon, which is an estimate: the next settlement can differ."""

    def __init__(self, terms: ExchangeTerms, funding: FundingView) -> None:
        self._maker = terms.maker_fee
        self._taker = terms.taker_fee
        self._rate = funding.rate

    def fees(self) -> tuple[Decimal, Decimal]:
        return self._maker, self._taker

    def funding_estimate(self, position: Decimal, horizon: timedelta) -> Decimal | None:
        if self._rate is None:
            return None
        intervals = Decimal(horizon.total_seconds()) / Decimal(
            FUNDING_INTERVAL.total_seconds()
        )
        return position * self._rate * intervals

    def breakeven_step_fraction(self) -> Decimal:
        return 2 * self._maker
