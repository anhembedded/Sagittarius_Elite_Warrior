"""`EPIC-028F` — the leverage a Futures symbol now uses, as the exchange
confirmed it."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class LeverageSetting:
    """The exchange's answer to a leverage change: the leverage in effect and
    the largest position notional it allows at that leverage."""

    symbol: str
    leverage: int
    max_notional: Decimal
