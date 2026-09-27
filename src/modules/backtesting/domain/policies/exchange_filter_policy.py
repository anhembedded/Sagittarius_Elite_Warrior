from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.entry_rejection_reason import (
    EntryRejectionReason,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exchange_filters import (
    ExchangeFilters,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    NotionalCheck,
    OrderQuantityRoundingPolicy,
)


def _decimal(value: float) -> Decimal:
    """`repr()` rather than `Decimal(value)`: a float's shortest round-trip
    text is the number a user or an exchange wrote (`0.3`), while its exact
    binary expansion (`0.29999999999999998889…`) would floor one step short."""
    return Decimal(repr(value))


class ExchangeFilterPolicy:
    """
    @brief Domain policy applying one symbol's exchange order rules to a
    simulated entry (`EPIC-027C`, ADR D5): floor the quantity to the step
    size, then refuse an entry below the minimum quantity or notional.
    @details The arithmetic is the live order path's own
    `OrderQuantityRoundingPolicy` (published in `trading/contracts/`), so a
    backtest and a live order can never round the same symbol differently.
    `filters is None` means no metadata was known for the run: nothing is
    floored or refused, and the run's result says so.

    Extension cases, each a local change: MARKET_LOT_SIZE for market orders
    (a second step in `floor_quantity()`); a maximum quantity (one more
    `EntryRejectionReason` and one comparison); rounding stop prices to the
    tick (a method beside these, over `round_price_to_tick()`).
    """

    def __init__(
        self,
        filters: ExchangeFilters | None,
        rounding: OrderQuantityRoundingPolicy | None = None,
    ) -> None:
        self._filters = filters
        self._rounding = rounding or OrderQuantityRoundingPolicy()

    def floor_quantity(self, quantity: float) -> float:
        if self._filters is None:
            return quantity
        floored = self._rounding.round_quantity_down(
            _decimal(quantity), _decimal(self._filters.step_size)
        )
        return float(floored)

    def rejection_for(
        self, quantity: float, price: float
    ) -> EntryRejectionReason | None:
        """@brief The rule an already-floored entry fails, or `None`."""
        if self._filters is None:
            return None
        if quantity <= 0 or quantity < self._filters.min_quantity:
            return EntryRejectionReason.BELOW_MIN_QUANTITY
        notional = self._rounding.is_notional_sufficient(
            _decimal(quantity), _decimal(price), _decimal(self._filters.min_notional)
        )
        if notional is NotionalCheck.INSUFFICIENT:
            return EntryRejectionReason.BELOW_MIN_NOTIONAL
        return None
