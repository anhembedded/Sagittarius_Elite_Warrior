"""`EPIC-039G` — Spot's `ICostModel`: the account's maker and taker rates, and no funding."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_cost_model import ICostModel
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)


class SpotCostModel(ICostModel):
    """Spot charges a fee per fill and nothing for holding, so its funding is zero **by
    definition** (no funding exists), not because a rate was read as zero."""

    def __init__(self, terms: ExchangeTerms) -> None:
        self._maker = terms.maker_fee
        self._taker = terms.taker_fee

    def fees(self) -> tuple[Decimal, Decimal]:
        return self._maker, self._taker

    def funding_estimate(self, position: Decimal, horizon: timedelta) -> Decimal | None:
        return Decimal(0)

    def breakeven_step_fraction(self) -> Decimal:
        return 2 * self._maker
