"""`EPIC-021C`/`EPIC-027I` — one symbol's live order-rounding rules,
market-neutral: `FuturesMetadataProvider` and `SpotMetadataProvider` both
return this same type, chosen at composition by the active `TradingVenue`.

@details Deliberately separate from `SymbolMarketMetadata` (`BOT-095E1`),
which serves the backtest broker's float-shaped model across both markets
at once — the live side needs `Decimal` (`stepSize`/`tickSize` values like
`"0.001"` must round exactly the way the exchange does, and comparing them
as `float` is the exact trap `ONBOARDING.md` §8 already names from a real
prior incident in this repo), so the two parsers apply the same Binance
filter-reading rules independently rather than sharing one implementation
across the `trading`/`market_data` module boundary
(`architecture-rule.md` §3).

`quantity_precision`/`price_precision` are `None` for Spot: Binance's Spot
`exchangeInfo` carries no equivalent of Futures' symbol-level display
precision fields, and nothing invents one. `market_step_size` is `None`
whenever the venue's `exchangeInfo` carries no `MARKET_LOT_SIZE` filter for
that symbol, or reports one with a `"0"` `stepSize` (Binance's own
convention for "no restriction from this filter" — confirmed live on Spot
Testnet's real `BTCUSDT`, `BUG-138`) — every symbol this app has seen also
has `LOT_SIZE`, which `step_size_for()` falls back to in both cases.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import (
    OrderType,
)

_DEFAULT_METADATA_MAX_AGE_SECONDS = 86400.0  # 24 hours


@dataclass(frozen=True)
class SymbolOrderMetadata:
    """Immutable snapshot of one symbol's order-rounding rules."""

    symbol: str
    status: str
    step_size: Decimal
    tick_size: Decimal
    min_notional: Decimal
    quantity_precision: int | None
    price_precision: int | None
    fetched_at: datetime
    #: `MARKET_LOT_SIZE`'s own step size — distinct from `LOT_SIZE`'s
    #: `step_size` above. `None` when the venue reports no such filter for
    #: this symbol (every Futures symbol today; Spot only when the filter
    #: is genuinely absent from `exchangeInfo`).
    market_step_size: Decimal | None = None

    def is_stale(
        self,
        max_age_seconds: float = _DEFAULT_METADATA_MAX_AGE_SECONDS,
        now: datetime | None = None,
    ) -> bool:
        current_time = now or datetime.now(UTC)
        age = (current_time - self.fetched_at).total_seconds()
        return age > max_age_seconds

    def step_size_for(self, order_type: OrderType) -> Decimal:
        """@brief The lot-size step a given order type must round to.
        @details `OrderType.MARKET` uses `MARKET_LOT_SIZE`'s step when the
        exchange publishes one for this symbol, falling back to `LOT_SIZE`
        otherwise — the same fallback Binance's own matching engine applies
        when a symbol has no separate market-order lot filter. Every other
        order type uses `LOT_SIZE` directly (`EPIC-027I`'s own acceptance
        criterion: "a LIMIT order with `LOT_SIZE`").
        """
        if order_type is OrderType.MARKET and self.market_step_size is not None:
            return self.market_step_size
        return self.step_size
