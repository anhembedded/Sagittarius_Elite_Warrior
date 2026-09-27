"""`EPIC-027H` — a Spot balance for one asset: exactly what `GET
/api/v3/account`'s `balances` array gives, no more. Never a `LivePosition`
with invented fields (ADR D7; `domain-truth-rule.md`) — Spot has no entry
price, mark price, leverage or liquidation price to report.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class SpotHolding:
    """One asset's balance on a Spot account.

    @details `dust_threshold` travels with the holding rather than living
    as a hidden module constant, so a consumer reading `is_dust` sees the
    exact threshold that produced it without a second import.
    """

    asset: str
    free: Decimal
    locked: Decimal
    dust_threshold: Decimal

    @property
    def total(self) -> Decimal:
        """Free plus locked — the whole balance, matching the account-wide
        `walletBalance` semantics `ExchangeConnectionStatus.usdt_balance`
        already carries for Futures."""
        return self.free + self.locked

    @property
    def is_dust(self) -> bool:
        """True when this holding is at or below its own dust threshold —
        too small to be a meaningful position, whatever its price."""
        return self.total <= self.dust_threshold
