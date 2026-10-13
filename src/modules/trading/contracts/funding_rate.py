"""`EPIC-039G` — a Futures symbol's funding rate and when it is next settled."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class FundingRate:
    """`GET /fapi/v1/premiumIndex`'s `lastFundingRate` and `nextFundingTime`.

    @details `rate` is a fraction per funding interval (every 8 hours on the
    exchange's default schedule), signed: positive means longs pay shorts,
    negative the reverse. It is the latest settled rate, which the next
    settlement can differ from; a caller labels it an estimate."""

    symbol: str
    rate: Decimal
    next_funding_at: datetime
    #: When the exchange computed the answer.
    as_of: datetime
