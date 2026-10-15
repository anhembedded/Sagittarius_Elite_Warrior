"""`BUG-210` — the one shape every sentence of Grid advice has.

A person cannot act on "The range is 4.72 daily ATRs wide, outside 2–4": it names a ratio
and a band, never the money behind them, never what to do. Advice is a `WARNING` whose
whole text is written here, in four parts, each required:

  · `finding` — what was measured, as the real number with its unit, beside the value the
    threshold asks for expressed the same way (a price, an amount of quote) and not only as
    a ratio; a term such as ATR is defined where it first appears;
  · `consequence` — what it means for the bot, in plain words;
  · `action` — what to change, with a concrete value or the button that proposes one;
  · `ADVICE_TAIL` — that nothing blocks Start.

Seam now, variant later: a new check builds an `Advice` and a new unit is a field of
`Figures`; no sentence is assembled by hand in a check. A blank part raises, so a message
cannot be added without saying all four things.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
    MarketView,
)

ADVICE_TAIL = "This is advice; the bot can still be created."

_UNKNOWN_QUOTE = "quote"
_UNKNOWN_BASE = "The asset"


@dataclass(frozen=True, slots=True)
class Advice:
    """One piece of advice, in the four parts a person needs to act on it."""

    finding: str
    consequence: str
    action: str

    def __post_init__(self) -> None:
        for name in ("finding", "consequence", "action"):
            if not getattr(self, name).strip():
                raise ValueError(f"advice needs a {name}")

    @property
    def text(self) -> str:
        return f"{self.finding} {self.consequence} {self.action} {ADVICE_TAIL}"


@dataclass(frozen=True, slots=True)
class Figures:
    """Writes a number the way the venue prices it: to the tick, without padding zeros, with
    the symbol's own asset names (`MarketView.base_asset`, `quote_asset`)."""

    tick: Decimal
    base_asset: str
    quote_asset: str

    @classmethod
    def of(cls, terms: ExchangeTerms, market: MarketView) -> Figures:
        return cls(terms.tick_size, market.base_asset, market.quote_asset)

    @property
    def unit(self) -> str:
        return self.quote_asset or _UNKNOWN_QUOTE

    @property
    def base(self) -> str:
        return self.base_asset or _UNKNOWN_BASE

    def snap(self, price: Decimal) -> Decimal:
        """`price` on the nearest tick, never below one tick."""
        ticks = (price / self.tick).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        return max(ticks, Decimal(1)) * self.tick

    def price(self, price: Decimal) -> str:
        """`2371.98`, not `2371.98000000`; `2400`, not `2.4E+3`."""
        return plain(self.snap(price))

    def money(self, amount: Decimal) -> str:
        return f"{self.price(amount)} {self.unit}"

    def span(self, low: Decimal, high: Decimal) -> str:
        return f"{self.price(low)}–{self.price(high)} {self.unit}"


def plain(value: Decimal) -> str:
    """A decimal as digits only: no exponent, no trailing zeros."""
    normal = value.normalize()
    return f"{normal:f}"
