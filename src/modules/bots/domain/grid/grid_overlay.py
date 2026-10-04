"""`EPIC-029G` — what a Grid draws on its chart, from its plan and, when it
has run, from what it did (ADR D16).

One computation for the three surfaces: the planner preview passes only the
plan; the backtest (`EPIC-029D`) and the running bot (`EPIC-029E`) add a
`GridActivity`, the levels' current states, the fills and the average cost.
The drawer then draws whatever this returns, so a backtest and a live bot
with the same activity draw the same chart.

· **Levels** take their role from the activity's state when there is one,
  else from the plan's side (`BUY`, `SELL`, `EMPTY`).
· **Range edges** are the user's lower and upper limits, beside the rounded
  levels nearest them.
· **ATR zones** (with a daily ATR): where each edge sits if the range is
  `range_atr_low`–`range_atr_high` daily ATRs wide **and centred on the last
  price**. The range-versus-ATR check judges the width alone
  (`grid_checks.check_range_against_atr`); centring is this drawing's own
  suggestion. A zone never reaches below zero.
· **Bollinger** (when the caller computed the bands): the band between them.

Lines sort by price, then role, then label, so equal prices draw in one
stable order everywhere.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from types import MappingProxyType

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import (
    BotOverlay,
    OverlayBand,
    OverlayBandRole,
    OverlayFill,
    OverlayLine,
    OverlayRole,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    GridLevel,
    GridPlan,
    LevelSide,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)

_TWO = Decimal(2)


class LevelState(str, Enum):
    """What a level holds now, once the bot has run."""

    RESTING_BUY = "RESTING_BUY"
    RESTING_SELL = "RESTING_SELL"
    EMPTY = "EMPTY"
    #: Its resting order has partly filled.
    PARTIAL = "PARTIAL"


_PLAN_ROLES = {
    LevelSide.BUY: OverlayRole.BUY_LEVEL,
    LevelSide.SELL: OverlayRole.SELL_LEVEL,
    LevelSide.EMPTY: OverlayRole.EMPTY_LEVEL,
}
_STATE_ROLES = {
    LevelState.RESTING_BUY: OverlayRole.BUY_LEVEL,
    LevelState.RESTING_SELL: OverlayRole.SELL_LEVEL,
    LevelState.EMPTY: OverlayRole.EMPTY_LEVEL,
    LevelState.PARTIAL: OverlayRole.PARTIAL_LEVEL,
}


@dataclass(frozen=True, slots=True)
class GridActivity:
    """What a Grid has done, as a backtest or the live executor reports it."""

    #: Each level's state, by level index; a level not named keeps its
    #: plan's side.
    level_states: Mapping[int, LevelState] = field(default_factory=dict)
    fills: tuple[OverlayFill, ...] = ()
    #: The average cost of the base the bot holds; `None` when it holds none.
    average_cost: Decimal | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "level_states", MappingProxyType(dict(self.level_states))
        )


@dataclass(frozen=True, slots=True)
class BollingerBands:
    """The lower and upper Bollinger band at the last candle."""

    lower: Decimal
    upper: Decimal


@dataclass(frozen=True, slots=True)
class GridOverlaySource:
    """Everything a Grid's overlay is computed from (`code/quality.md` §7)."""

    params: GridParams
    plan: GridPlan
    thresholds: GridThresholds
    activity: GridActivity | None = None
    daily_atr: Decimal | None = None
    bollinger: BollingerBands | None = None


def grid_overlay(source: GridOverlaySource) -> BotOverlay:
    """@brief The Grid's lines, bands and fills for one surface."""
    activity = source.activity or GridActivity()
    lines = [_level_line(level, activity) for level in source.plan.levels]
    lines += _edge_lines(source.params)
    lines += _exit_lines(source.params)
    if activity.average_cost is not None:
        lines.append(
            OverlayLine(activity.average_cost, OverlayRole.AVERAGE_COST, "Avg")
        )
    bands = _atr_zones(source) + _bollinger(source.bollinger)
    return BotOverlay(
        lines=tuple(sorted(lines, key=_line_order)),
        bands=tuple(sorted(bands, key=lambda band: (band.lower, band.upper))),
        fills=tuple(sorted(activity.fills, key=lambda fill: fill.time)),
    )


def _level_line(level: GridLevel, activity: GridActivity) -> OverlayLine:
    state = activity.level_states.get(level.index)
    role = _PLAN_ROLES[level.side] if state is None else _STATE_ROLES[state]
    return OverlayLine(level.price, role, f"L{level.index}")


def _edge_lines(params: GridParams) -> list[OverlayLine]:
    return [
        OverlayLine(params.lower, OverlayRole.RANGE_EDGE, "Lower"),
        OverlayLine(params.upper, OverlayRole.RANGE_EDGE, "Upper"),
    ]


def _exit_lines(params: GridParams) -> list[OverlayLine]:
    lines = []
    if params.stop_loss_price is not None:
        lines.append(OverlayLine(params.stop_loss_price, OverlayRole.STOP_LOSS, "SL"))
    if params.take_profit_price is not None:
        lines.append(
            OverlayLine(params.take_profit_price, OverlayRole.TAKE_PROFIT, "TP")
        )
    return lines


def _atr_zones(source: GridOverlaySource) -> list[OverlayBand]:
    atr = source.daily_atr
    if atr is None or atr <= 0:
        return []
    last = source.plan.last_price
    near = source.thresholds.range_atr_low * atr / _TWO
    far = source.thresholds.range_atr_high * atr / _TWO
    zero = Decimal(0)
    return [
        OverlayBand(
            max(last - far, zero),
            max(last - near, zero),
            OverlayBandRole.ATR_ZONE,
            "Lower by ATR",
        ),
        OverlayBand(last + near, last + far, OverlayBandRole.ATR_ZONE, "Upper by ATR"),
    ]


def _bollinger(bands: BollingerBands | None) -> list[OverlayBand]:
    if bands is None:
        return []
    return [OverlayBand(bands.lower, bands.upper, OverlayBandRole.BOLLINGER, "BB")]


def _line_order(line: OverlayLine) -> tuple[Decimal, str, str]:
    return (line.price, line.role.value, line.label)
