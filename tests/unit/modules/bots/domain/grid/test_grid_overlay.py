"""`EPIC-029G` — a Grid's overlay, computed from the report's example plan
(BTC at 65,000, 60,000–70,000, 10 grids, exits 5% beyond the range)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import (
    FillSide,
    OverlayBand,
    OverlayBandRole,
    OverlayFill,
    OverlayRole,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    evaluate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_overlay import (
    BollingerBands,
    GridActivity,
    GridOverlaySource,
    LevelState,
    grid_overlay,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    inputs,
)


def _source(**extra: object) -> GridOverlaySource:
    evaluation = evaluate_grid(inputs(), GridThresholds())
    assert evaluation.params is not None and evaluation.plan is not None
    return GridOverlaySource(
        evaluation.params,
        evaluation.plan,
        GridThresholds(),
        **extra,  # type: ignore[arg-type]
    )


def _by_role(source: GridOverlaySource, role: OverlayRole) -> list[Decimal]:
    return [line.price for line in grid_overlay(source).lines if line.role is role]


def test_the_plan_alone_draws_its_levels_edges_and_exits() -> None:
    source = _source()

    assert _by_role(source, OverlayRole.BUY_LEVEL) == [
        Decimal(60000),
        Decimal(61000),
        Decimal(62000),
        Decimal(63000),
        Decimal(64000),
    ]
    assert _by_role(source, OverlayRole.EMPTY_LEVEL) == [Decimal(65000)]
    assert len(_by_role(source, OverlayRole.SELL_LEVEL)) == 5
    assert _by_role(source, OverlayRole.RANGE_EDGE) == [Decimal(60000), Decimal(70000)]
    assert _by_role(source, OverlayRole.STOP_LOSS) == [Decimal(57000)]
    assert _by_role(source, OverlayRole.TAKE_PROFIT) == [Decimal(73500)]
    assert _by_role(source, OverlayRole.AVERAGE_COST) == []
    assert grid_overlay(source).bands == ()
    assert grid_overlay(source).fills == ()


def test_the_activity_decides_a_levels_role() -> None:
    """Level 4 (64,000) filled its buy and now rests a sell; level 7 is
    half filled. The others keep their plan's side."""
    activity = GridActivity(
        level_states={4: LevelState.RESTING_SELL, 7: LevelState.PARTIAL}
    )
    overlay = grid_overlay(_source(activity=activity))

    roles = {line.label: line.role for line in overlay.lines if line.label[0] == "L"}
    assert roles["L4"] is OverlayRole.SELL_LEVEL
    assert roles["L7"] is OverlayRole.PARTIAL_LEVEL
    assert roles["L3"] is OverlayRole.BUY_LEVEL
    assert roles["L5"] is OverlayRole.EMPTY_LEVEL


def test_the_average_cost_and_the_fills_oldest_first() -> None:
    later = OverlayFill(
        datetime(2026, 10, 4, 12, tzinfo=UTC), Decimal(65000), FillSide.SELL, "L5"
    )
    earlier = OverlayFill(
        datetime(2026, 10, 4, 9, tzinfo=UTC), Decimal(64000), FillSide.BUY, "L4"
    )
    activity = GridActivity(fills=(later, earlier), average_cost=Decimal("63500.5"))

    overlay = grid_overlay(_source(activity=activity))

    assert overlay.fills == (earlier, later)
    assert _by_role(_source(activity=activity), OverlayRole.AVERAGE_COST) == [
        Decimal("63500.5")
    ]


def test_the_atr_zones_are_where_the_edges_sit_at_two_to_four_atrs() -> None:
    """Daily ATR 2,500 around 65,000: a range 2–4 ATRs wide puts the lower
    limit in 60,000–62,500 and the upper in 67,500–70,000."""
    overlay = grid_overlay(_source(daily_atr=Decimal(2500)))

    assert overlay.bands == (
        OverlayBand(
            Decimal(60000), Decimal(62500), OverlayBandRole.ATR_ZONE, "Lower by ATR"
        ),
        OverlayBand(
            Decimal(67500), Decimal(70000), OverlayBandRole.ATR_ZONE, "Upper by ATR"
        ),
    )


def test_bollinger_bands_draw_between_them() -> None:
    overlay = grid_overlay(
        _source(bollinger=BollingerBands(Decimal(61200), Decimal(68800)))
    )

    assert [(band.role, band.lower, band.upper) for band in overlay.bands] == [
        (OverlayBandRole.BOLLINGER, Decimal(61200), Decimal(68800))
    ]


def test_equal_prices_draw_in_one_stable_order() -> None:
    """60,000 is both level L0 and the lower edge: the order is by price,
    then role, so every surface lists them the same way."""
    lines = grid_overlay(_source()).lines

    at_lower = [(line.role, line.label) for line in lines if line.price == 60000]
    assert at_lower == [
        (OverlayRole.BUY_LEVEL, "L0"),
        (OverlayRole.RANGE_EDGE, "Lower"),
    ]
    assert [line.price for line in lines] == sorted(line.price for line in lines)


def test_an_atr_zone_never_reaches_below_zero() -> None:
    """The PR #321 review: a daily ATR larger than half the price would put
    the lower zone under zero."""
    lower_zone = grid_overlay(_source(daily_atr=Decimal(40000))).bands[0]

    assert lower_zone.lower == Decimal(0)
    assert lower_zone.upper == Decimal(25000)
