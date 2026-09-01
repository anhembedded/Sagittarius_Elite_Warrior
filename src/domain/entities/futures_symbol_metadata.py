"""`EPIC-021C` — USD-M Futures exchange rules for one symbol.

@details Deliberately separate from `SymbolMarketMetadata` (`BOT-095E1`),
which serves the backtest broker's spot-shaped model. Futures adds
`quantity_precision`/`price_precision` spot never had, and mixing the two
would force every backtest call site to understand a concept it never uses
(`EPIC-021C` task file §2.1). `Decimal`, not `float` — `stepSize`/`tickSize`
values like `"0.001"` must round exactly the way the exchange does, and
comparing them as `float` is the exact trap `ONBOARDING.md` §8 already
names from a real prior incident in this repo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

_DEFAULT_METADATA_MAX_AGE_SECONDS = 86400.0  # 24 hours


@dataclass(frozen=True)
class FuturesSymbolMetadata:
    """Immutable snapshot of one USD-M Futures symbol's order-rounding rules."""

    symbol: str
    status: str
    step_size: Decimal
    tick_size: Decimal
    min_notional: Decimal
    quantity_precision: int
    price_precision: int
    fetched_at: datetime

    def is_stale(
        self,
        max_age_seconds: float = _DEFAULT_METADATA_MAX_AGE_SECONDS,
        now: datetime | None = None,
    ) -> bool:
        current_time = now or datetime.now(UTC)
        age = (current_time - self.fetched_at).total_seconds()
        return age > max_age_seconds
