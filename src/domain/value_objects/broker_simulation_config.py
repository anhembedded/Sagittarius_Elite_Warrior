from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.domain.value_objects.commission_type import (
    CommissionType,
)

_PERCENT_UPPER_BOUND = 100.0


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
    #: BOT-105A — % profit from entry (in the position's favor) that moves
    #: `stop_loss_price` to the raw entry price, one time. `None` (default)
    #: disables break-even entirely.
    breakeven_trigger_pct: float | None = None
    #: BOT-105A — % profit from entry that arms trailing; once armed, the
    #: stop ratchets to `trailing_offset_pct` behind the best price seen
    #: since entry and never moves back. Must be set together with
    #: `trailing_offset_pct` (both or neither) — an activation threshold
    #: with no offset, or vice versa, doesn't describe a trailing stop.
    trailing_activation_pct: float | None = None
    #: BOT-105A — % distance the trailing stop trails behind the best
    #: price seen since entry. See `trailing_activation_pct`.
    trailing_offset_pct: float | None = None
    #: BOT-105A — ordered `(profit_pct, size_fraction)` levels for scaling
    #: out of a position (e.g. `((2.0, 0.5), (4.0, 0.5))` closes half the
    #: *original* position size at +2% and the rest at +4%). Order in the
    #: tuple doesn't matter — `PaperExchange` sorts ascending by
    #: `profit_pct`. Fractions need not sum to `1.0`; whatever's left after
    #: the last configured level keeps running with no further TP. `None`
    #: (default) disables partial take-profit; when set, it replaces
    #: `take_profit_pct` for that run (the two are mutually exclusive per
    #: position — a single all-or-nothing target is a degenerate case of
    #: scaling out, so there's nothing a combination of both would mean
    #: that `tp_levels` alone can't already express).
    tp_levels: tuple[tuple[float, float], ...] | None = None

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
        if self.breakeven_trigger_pct is not None and self.breakeven_trigger_pct <= 0:
            raise ValueError(
                "breakeven_trigger_pct must be positive, got "
                f"{self.breakeven_trigger_pct}"
            )
        if (self.trailing_activation_pct is None) != (self.trailing_offset_pct is None):
            raise ValueError(
                "trailing_activation_pct and trailing_offset_pct must be set "
                "together (both or neither), got "
                f"trailing_activation_pct={self.trailing_activation_pct}, "
                f"trailing_offset_pct={self.trailing_offset_pct}"
            )
        if (
            self.trailing_activation_pct is not None
            and self.trailing_activation_pct <= 0
        ):
            raise ValueError(
                "trailing_activation_pct must be positive, got "
                f"{self.trailing_activation_pct}"
            )
        if self.trailing_offset_pct is not None and not (
            0 < self.trailing_offset_pct < _PERCENT_UPPER_BOUND
        ):
            raise ValueError(
                f"trailing_offset_pct must be in (0, 100), got {self.trailing_offset_pct}"
            )
        if self.tp_levels is not None:
            if len(self.tp_levels) == 0:
                raise ValueError(
                    "tp_levels must not be empty when set, use None instead"
                )
            fraction_total = 0.0
            for profit_pct, size_fraction in self.tp_levels:
                if profit_pct <= 0:
                    raise ValueError(
                        f"tp_levels profit_pct must be positive, got {profit_pct}"
                    )
                if not (0 < size_fraction <= 1.0):
                    raise ValueError(
                        f"tp_levels size_fraction must be in (0, 1], got {size_fraction}"
                    )
                fraction_total += size_fraction
            if fraction_total > 1.0 + 1e-9:
                raise ValueError(
                    "tp_levels size_fraction values must not sum to more than "
                    f"1.0, got {fraction_total}"
                )
