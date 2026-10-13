"""`EPIC-039K` — one settled funding charge of a USD-M perpetual, as the exchange recorded it.

@details `GET /fapi/v1/fundingRate` (read 2026-10-13 on Binance's page): `fundingRate` is a
fraction of the position's notional, signed (positive: longs pay shorts), `fundingTime` is the
settlement instant, `markPrice` is the mark price the charge was computed at. `markPrice` was
added to the endpoint on 2023-11-01, so an earlier record has none: `mark_price` is `None`
then, never a guess, and the caller says which price it charged on instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class FundingEvent:
    """A funding settlement of `symbol` at `time`."""

    symbol: str
    time: datetime
    #: A fraction of the position's notional; positive means longs pay shorts.
    rate: Decimal
    #: The mark price the exchange charged on; `None` for a record that predates the field.
    mark_price: Decimal | None

    def __post_init__(self) -> None:
        if self.time.tzinfo is None:
            raise ValueError("a funding time needs a timezone-aware instant")
        if self.mark_price is not None and self.mark_price <= 0:
            raise ValueError("a mark price is positive when it is known")


class FundingHistoryUnavailableError(RuntimeError):
    """The funding history of a symbol could not be read.

    `reason` is a sentence a person can read ("Spot has no funding", "the exchange did not
    answer"); a caller shows it or decides what a backtest without funding means.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
