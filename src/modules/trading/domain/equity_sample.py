"""`EPIC-021M` §2.2 — one point on the live equity curve.

@details Equity at a moment in time is `walletBalance + unrealizedPnL`,
read straight off Binance's own `ACCOUNT_UPDATE` stream (no persistence,
no derived/estimated fields). The addition itself is the one domain
calculation this task's design section calls out explicitly ("một phép
tính domain thuần") — it must be testable with no network, so it lives
here as a property, not inline in the parser or the chart widget.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class EquitySample:
    """@brief `(captured_at, wallet_balance, unrealized_pnl)` — `total` is
    the (thời điểm, vốn) point the live equity chart plots."""

    captured_at: datetime
    wallet_balance: Decimal
    unrealized_pnl: Decimal

    @property
    def total(self) -> Decimal:
        return self.wallet_balance + self.unrealized_pnl
