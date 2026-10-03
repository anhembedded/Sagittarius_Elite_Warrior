"""`EPIC-029C` — where the levels fall, for the two spacing models (the report, PRO-006 §1.5).

  · **Arithmetic:** `step = (U − L) / N`, level `i` at `L + i × step`.
    Every grid earns the same price step, so its percentage shrinks towards
    the top: `step / buy − 2 × fee`.
  · **Geometric:** `ratio = (U / L) ^ (1 / N)`, level `i` at `L × ratio^i`.
    Every grid earns the same percentage, `ratio − 1 − 2 × fee`.

`N` grids make `N + 1` levels, from `L` to `U` inclusive; the last level is set
to `U` exactly, so the geometric product's last digit never moves the range.
The prices here are raw; `grid_plan.py` rounds them to the tick, by side.
"""

from __future__ import annotations

from decimal import Decimal, localcontext

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridSpacing,
)

#: Digits for the geometric power: far beyond any tick size, so rounding to the
#: tick is the only rounding a level price sees.
_PRECISION = 40


def arithmetic_step(lower: Decimal, upper: Decimal, grid_count: int) -> Decimal:
    return (upper - lower) / grid_count


def geometric_ratio(lower: Decimal, upper: Decimal, grid_count: int) -> Decimal:
    with localcontext() as context:
        context.prec = _PRECISION
        return ((upper / lower).ln() / grid_count).exp()


def raw_levels(
    lower: Decimal, upper: Decimal, grid_count: int, spacing: GridSpacing
) -> tuple[Decimal, ...]:
    """`grid_count + 1` prices from `lower` to `upper`, lowest first."""
    if spacing is GridSpacing.ARITHMETIC:
        step = arithmetic_step(lower, upper, grid_count)
        inner = [lower + step * index for index in range(grid_count)]
    else:
        ratio = geometric_ratio(lower, upper, grid_count)
        with localcontext() as context:
            context.prec = _PRECISION
            inner = [lower * ratio**index for index in range(grid_count)]
    return (*inner, upper)
