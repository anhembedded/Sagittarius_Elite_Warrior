from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.commission_type import (
    CommissionType,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.partial_take_profit_level import (
    PartialTakeProfitLevel,
)

_PERCENT_UPPER_BOUND = 100.0
_FRACTION_UPPER_BOUND = 1.0


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
    #: BOT-105A — % profit-of-margin (`OpenPosition.mfe_percent`'s own
    #: convention, same as `Trade.pnl_percent`) at which `PaperExchange`
    #: moves `stop_loss_price` to break-even (`entry_price`, ignoring
    #: fees) exactly once, locking in a zero-loss floor. `None` (default)
    #: disables it entirely — every position behaves exactly as it did
    #: before this field existed.
    break_even_trigger_pct: float | None = None
    #: BOT-105A — % profit-of-margin (`OpenPosition.mfe_percent`'s own
    #: convention, same as `break_even_trigger_pct`) at which the trailing
    #: stop arms and starts tracking the position's best-seen price. `0.0`
    #: arms from the very first bar after entry. Must be set together with
    #: `trailing_offset_pct` — one without the other is not a coherent
    #: configuration. `None` (default) disables trailing entirely.
    trailing_activation_pct: float | None = None
    #: BOT-105A — % distance of PRICE (not margin — compared directly
    #: against the running peak/trough, the same unit as
    #: `stop_loss_pct`/`take_profit_pct`) that the stop trails behind the
    #: position's best price once armed. Must be set together with
    #: `trailing_activation_pct`.
    trailing_offset_pct: float | None = None
    #: BOT-105C — ordered scale-out levels: at each level's `price_pct` %
    #: distance from entry (same convention as `stop_loss_pct`/
    #: `take_profit_pct`), close that level's `close_fraction` of the
    #: ORIGINAL entry quantity, leaving the remainder open. `()` (default)
    #: disables Partial Take Profit entirely. Mutually exclusive with
    #: `take_profit_pct` — a single full take-profit and a scale-out ladder
    #: both configure "how this position takes profit"; combining them is
    #: an interaction this task was never asked to define.
    partial_take_profit_levels: tuple[PartialTakeProfitLevel, ...] = field(
        default_factory=tuple
    )

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
        if self.stop_loss_pct is not None and not (
            0 < self.stop_loss_pct < _PERCENT_UPPER_BOUND
        ):
            raise ValueError(
                f"stop_loss_pct must be in (0, 100), got {self.stop_loss_pct}"
            )
        if self.take_profit_pct is not None and self.take_profit_pct <= 0:
            raise ValueError(
                f"take_profit_pct must be positive, got {self.take_profit_pct}"
            )
        if self.break_even_trigger_pct is not None and self.break_even_trigger_pct <= 0:
            raise ValueError(
                "break_even_trigger_pct must be positive, got "
                f"{self.break_even_trigger_pct}"
            )
        if (self.trailing_activation_pct is None) != (self.trailing_offset_pct is None):
            raise ValueError(
                "trailing_activation_pct and trailing_offset_pct must be set "
                "together, got trailing_activation_pct="
                f"{self.trailing_activation_pct}, trailing_offset_pct="
                f"{self.trailing_offset_pct}"
            )
        if (
            self.trailing_activation_pct is not None
            and self.trailing_activation_pct < 0
        ):
            raise ValueError(
                "trailing_activation_pct must be non-negative, got "
                f"{self.trailing_activation_pct}"
            )
        if self.trailing_offset_pct is not None and not (
            0 < self.trailing_offset_pct < _PERCENT_UPPER_BOUND
        ):
            raise ValueError(
                f"trailing_offset_pct must be in (0, 100), got {self.trailing_offset_pct}"
            )
        if self.partial_take_profit_levels:
            if self.take_profit_pct is not None:
                raise ValueError(
                    "partial_take_profit_levels and take_profit_pct are mutually "
                    "exclusive — combining a scale-out ladder with a single "
                    "full take-profit is not a defined interaction"
                )
            price_pcts = [level.price_pct for level in self.partial_take_profit_levels]
            if price_pcts != sorted(price_pcts) or len(set(price_pcts)) != len(
                price_pcts
            ):
                raise ValueError(
                    "partial_take_profit_levels must be ordered by strictly "
                    f"increasing price_pct, got {price_pcts}"
                )
            total_fraction = sum(
                level.close_fraction for level in self.partial_take_profit_levels
            )
            if total_fraction > _FRACTION_UPPER_BOUND:
                raise ValueError(
                    "partial_take_profit_levels close_fraction values must sum "
                    f"to at most 1.0, got {total_fraction}"
                )
