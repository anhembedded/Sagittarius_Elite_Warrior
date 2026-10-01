"""`EPIC-028O` — a Futures symbol's notional and leverage brackets.

@details `GET /fapi/v1/leverageBracket` lists, per symbol, the notional
bands Binance sizes leverage and maintenance margin by. A bracket covers
notionals from its floor up to its cap: the higher the notional, the lower
the leverage allowed and the higher the maintenance-margin rate. The
Futures desk caps its leverage slider with the first bracket and reads the
maintenance rate and amount (`cum`) the liquidation estimate needs
(`LiquidationTerms`) from the bracket a position's notional falls in.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.estimate_inputs import (
    require_not_negative,
)


@dataclass(frozen=True)
class LeverageBracket:
    """One notional band."""

    bracket: int
    initial_leverage: int
    notional_floor: Decimal
    notional_cap: Decimal
    #: As a fraction (`0.004` is 0.4 %).
    maintenance_margin_rate: Decimal
    #: Binance's `cum`, the maintenance amount; zero on the first bracket.
    maintenance_amount: Decimal

    def __post_init__(self) -> None:
        if self.initial_leverage < 1:
            raise ValueError(
                f"initial_leverage must be 1 or more, got {self.initial_leverage}"
            )
        require_not_negative("notional_floor", self.notional_floor)
        if self.notional_cap <= self.notional_floor:
            raise ValueError(
                f"bracket {self.bracket}: cap {self.notional_cap} is not above "
                f"floor {self.notional_floor}"
            )
        require_not_negative("maintenance_margin_rate", self.maintenance_margin_rate)
        require_not_negative("maintenance_amount", self.maintenance_amount)


@dataclass(frozen=True)
class LeverageBrackets:
    """Every bracket of one symbol, lowest notional first and without gaps."""

    symbol: str
    brackets: tuple[LeverageBracket, ...]

    def __post_init__(self) -> None:
        if not self.brackets:
            raise ValueError(f"{self.symbol}: no leverage brackets")
        for lower, upper in zip(self.brackets, self.brackets[1:], strict=False):
            if upper.notional_floor != lower.notional_cap:
                raise ValueError(
                    f"{self.symbol}: bracket {upper.bracket} starts at "
                    f"{upper.notional_floor}, not at the previous cap "
                    f"{lower.notional_cap}"
                )

    @property
    def max_leverage(self) -> int:
        """The highest leverage the symbol allows: the first bracket's."""
        return self.brackets[0].initial_leverage

    def bracket_for(self, notional: Decimal) -> LeverageBracket:
        """@return The bracket `notional` falls in: floor inclusive, cap
        exclusive; a notional past the last cap gets the last bracket."""
        require_not_negative("notional", notional)
        for bracket in self.brackets:
            if notional < bracket.notional_cap:
                return bracket
        return self.brackets[-1]
