from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.domain.value_objects.commission_type import (
    CommissionType,
)


@dataclass(frozen=True)
class BrokerSimulationConfig:
    """
    @brief Immutable configuration for broker execution and friction simulation (BOT-104).
    """

    slippage_ticks: int = (
        0  #: Number of price ticks slipped on market fills (default 0)
    )
    tick_size: float = (
        0.01  #: Minimum price increment per tick for the symbol (default $0.01)
    )
    commission_type: CommissionType = CommissionType.PERCENT  #: Fee model
    commission_value: float = 0.1  #: Fee value (e.g. 0.1% or $1.00)
    pyramiding: int = 1  #: Max allowed open positions in the same direction (default 1)
    long_leverage: float = 1.0  #: Long leverage / margin multiplier (default 1.0x)
    short_leverage: float = 1.0  #: Short leverage / margin multiplier (default 1.0x)
    #: BOT-041 — % distance from entry to the auto-close stop, e.g. `1.2`
    #: means 1.2%. `None` (default) disables stop-loss entirely — every
    #: position behaves exactly as it did before this field existed, only
    #: closing on a strategy SELL/COVER signal or `force_close()`.
    stop_loss_pct: float | None = None
    #: BOT-041 — % distance from entry to the auto-close target, e.g. `3.2`
    #: means 3.2%. `None` (default) disables take-profit entirely.
    take_profit_pct: float | None = None

    def __post_init__(self) -> None:
        if self.slippage_ticks < 0:
            raise ValueError(
                f"slippage_ticks must be non-negative, got {self.slippage_ticks}"
            )
        if self.tick_size <= 0:
            raise ValueError(f"tick_size must be positive, got {self.tick_size}")
        if self.commission_value < 0:
            raise ValueError(
                f"commission_value must be non-negative, got {self.commission_value}"
            )
        if self.pyramiding < 1:
            raise ValueError(f"pyramiding must be at least 1, got {self.pyramiding}")
        if self.long_leverage <= 0 or self.short_leverage <= 0:
            raise ValueError("leverage must be positive")
        if self.stop_loss_pct is not None and not (0 < self.stop_loss_pct < 100):
            raise ValueError(
                f"stop_loss_pct must be in (0, 100), got {self.stop_loss_pct}"
            )
        if self.take_profit_pct is not None and self.take_profit_pct <= 0:
            raise ValueError(
                f"take_profit_pct must be positive, got {self.take_profit_pct}"
            )
