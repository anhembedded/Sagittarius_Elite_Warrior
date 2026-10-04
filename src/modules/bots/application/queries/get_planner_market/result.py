"""`EPIC-029F` — the numbers a bot's panel judges its parameters against."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
    MarketView,
)


@dataclass(frozen=True, slots=True)
class SuggestedRange:
    """A lower and upper limit a suggestion button fills in, never written by
    the planner itself (the user's rule: the parameters are the user's)."""

    lower: Decimal
    upper: Decimal


@dataclass(frozen=True, slots=True)
class PlannerMarket:
    """What the venue and the stored candles say about one symbol.

    `terms` and `market` are `None` with `problem` naming why when the venue
    cannot be read (not enabled, an unknown symbol, no answer). The two
    suggestions are `None` when too few daily candles are stored."""

    terms: ExchangeTerms | None
    market: MarketView | None
    atr_range: SuggestedRange | None
    bollinger: SuggestedRange | None
    problem: str = ""
