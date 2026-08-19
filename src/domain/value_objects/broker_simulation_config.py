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
