"""One scale-out level for `BOT-105C` Partial Take Profit — its own file per
`architecture-rule.md` §5: a value object is one abstraction level, the same
reasoning `PositionSizing` already applies, not a case for folding into
`BrokerSimulationConfig` itself."""

from dataclasses import dataclass

_FRACTION_UPPER_BOUND = 1.0


@dataclass(frozen=True)
class PartialTakeProfitLevel:
    """
    @brief One scale-out level: at `price_pct` % away from entry (the same
    convention as `stop_loss_pct`/`take_profit_pct`), close `close_fraction`
    of the position's ORIGINAL entry quantity.
    @details Levels are ordered by increasing `price_pct` inside
    `BrokerSimulationConfig.partial_take_profit_levels` — this type only
    validates itself; the ordering and the sum-of-fractions ceiling are
    validated across the whole tuple there, where both are visible.
    """

    price_pct: float
    close_fraction: float

    def __post_init__(self) -> None:
        if self.price_pct <= 0:
            raise ValueError(f"price_pct must be positive, got {self.price_pct}")
        if not (0 < self.close_fraction <= _FRACTION_UPPER_BOUND):
            raise ValueError(
                f"close_fraction must be in (0, 1.0], got {self.close_fraction}"
            )
