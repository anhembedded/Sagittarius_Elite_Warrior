"""`EPIC-029G` — a Grid's overlay, computed from the report's example plan
(BTC at 65,000, 60,000–70,000, 10 grids, exits 5% beyond the range)."""

from __future__ import annotations

from dataclasses import replace
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
    # `BUG-207`: both limits are levels here (L0 and L10), so they draw as those levels.
    assert _by_role(source, OverlayRole.RANGE_EDGE) == []
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


def test_a_limit_that_is_a_level_draws_one_label_in_the_levels_colour() -> None:
    """`BUG-207`: 60,000 is both level L0 and the lower limit, 70,000 both L10 and the
    upper. Two tags at one price overprint at the chart's right edge and the later one
    hides the other, so each price gets one label, the level's, saying what else it is."""
    lines = grid_overlay(_source()).lines

    at_lower = [(line.role, line.label) for line in lines if line.price == 60000]
    at_upper = [(line.role, line.label) for line in lines if line.price == 70000]
    assert at_lower == [(OverlayRole.BUY_LEVEL, "L0 · range bottom")]
    assert at_upper == [(OverlayRole.SELL_LEVEL, "L10 · range top")]
    assert [line.price for line in lines] == sorted(line.price for line in lines)
    prices = [line.price for line in lines]
    assert len(prices) == len(set(prices))


def test_a_limit_between_levels_keeps_its_own_line() -> None:
    """A limit no level sits on (the lowest level is above it) is a second price: it
    keeps its range-edge line and label, and every level keeps its own."""
    source = _source()
    source = replace(source, params=replace(source.params, lower=Decimal(59500)))

    lines = grid_overlay(source).lines

    assert [
        (line.price, line.role, line.label)
        for line in lines
        if line.role is OverlayRole.RANGE_EDGE
    ] == [(Decimal(59500), OverlayRole.RANGE_EDGE, "range bottom")]
    assert [line.label for line in lines if line.price == 60000] == ["L0"]
    assert [line.label for line in lines if line.price == 70000] == ["L10 · range top"]


def test_every_level_keeps_a_label_when_the_limits_merge_into_it() -> None:
    lines = grid_overlay(_source()).lines

    labelled = {line.label.split(" · ")[0] for line in lines if line.label[0] == "L"}
    assert labelled == {f"L{index}" for index in range(11)}


def test_an_atr_zone_never_reaches_below_zero() -> None:
    """The PR #321 review: a daily ATR larger than half the price would put
    the lower zone under zero."""
    lower_zone = grid_overlay(_source(daily_atr=Decimal(40000))).bands[0]

    assert lower_zone.lower == Decimal(0)
    assert lower_zone.upper == Decimal(25000)


def test_a_position_plans_liquidation_is_drawn_as_an_estimate_per_side() -> None:
    """`EPIC-039J`: the chart draws what the Liquidation row says, labelled an estimate."""
    source = _source(liquidations=(("long", Decimal(52000)), ("short", Decimal(81000))))

    lines = [
        line
        for line in grid_overlay(source).lines
        if line.role is OverlayRole.LIQUIDATION
    ]

    assert [(line.price, line.label) for line in lines] == [
        (Decimal(52000), "Liq long (est.)"),
        (Decimal(81000), "Liq short (est.)"),
    ]


def test_a_plan_without_liquidation_draws_none() -> None:
    assert _by_role(_source(), OverlayRole.LIQUIDATION) == []


def test_range_labels_cannot_be_read_as_exits() -> None:
    """`BUG-207`: the take-profit and stop-loss keep their own roles and labels; no
    range-limit wording is "Up", "Upper", "TP" or "SL", merged or not."""
    source = _source()
    source = replace(source, params=replace(source.params, lower=Decimal(59500)))

    lines = grid_overlay(source).lines

    exits = {line.role: line.label for line in lines if line.label in ("TP", "SL")}
    assert exits == {OverlayRole.TAKE_PROFIT: "TP", OverlayRole.STOP_LOSS: "SL"}
    range_words = [
        line.label
        for line in lines
        if line.role is OverlayRole.RANGE_EDGE or "range" in line.label
    ]
    assert range_words == ["range bottom", "L10 · range top"]
