"""`EPIC-026L` — the figure the owner sets: an amount of one quote asset, or nothing.

The figure is the owner's and has no default (decision N3, `DECISION_2026-09-20_mainnet_venue.md`
§4a): unset means the cap is off. It is read from one text, `"500 USDT"`, so the unit travels with
the amount and a figure meant in one currency is never summed over bots that earn in another.

A text that is set but cannot be read is an error, never "off": a misspelt figure that silently
disabled the cap would be the failure the cap exists to prevent (`code/errors.md` §7).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

_SHAPE = re.compile(
    r"^\s*(?P<amount>[0-9]+(?:\.[0-9]+)?)\s+(?P<asset>[A-Za-z0-9]{2,12})\s*$"
)


class LossCapFigureError(ValueError):
    """The configured figure is set and unusable; the sentence says how to write it."""


@dataclass(frozen=True, slots=True)
class LossCapFigure:
    """The day's loss, in `quote_asset`, at which every bot is stopped."""

    amount: Decimal
    quote_asset: str

    def __post_init__(self) -> None:
        if not self.amount.is_finite() or self.amount <= 0:
            raise LossCapFigureError("the loss cap must be an amount above zero")
        if not self.quote_asset or self.quote_asset != self.quote_asset.upper():
            raise LossCapFigureError(
                "the loss cap's quote asset is upper case, e.g. USDT"
            )

    def covers(self, symbol: str) -> bool:
        """Whether a bot on `symbol` earns in this figure's quote asset (a Binance symbol is
        base then quote, so the quote is how it ends)."""
        return symbol.upper().endswith(self.quote_asset)

    def text(self) -> str:
        return f"{self.amount.normalize():f} {self.quote_asset}"


def parse_loss_cap_figure(text: object) -> LossCapFigure | None:
    """`None` when the owner set nothing (an absent key or blank text); the figure when set.

    @raise LossCapFigureError The text is set and is not `<amount> <QUOTE>`.
    """
    if text is None or (isinstance(text, str) and not text.strip()):
        return None
    found = _SHAPE.fullmatch(text) if isinstance(text, str) else None
    if found is None:
        raise LossCapFigureError(
            "the loss cap is written as an amount and its quote asset, e.g. '500 USDT'; "
            "leave it empty to switch the cap off"
        )
    try:
        amount = Decimal(found["amount"])
    except InvalidOperation:
        raise LossCapFigureError("the loss cap's amount is not a number") from None
    return LossCapFigure(amount, found["asset"].upper())
