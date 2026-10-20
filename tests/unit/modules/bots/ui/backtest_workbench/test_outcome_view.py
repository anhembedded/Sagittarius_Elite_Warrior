"""`EPIC-040D` — what the chart takes from a kind-neutral outcome: its candles, and the kind's overlay
with the replay's own fills on top, each on the side it was filled."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_kind_backtester import (
    outcome_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.sandbox_plan import (
    SandboxPlan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import FillSide
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import GridKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.outcome_view import (
    chart_candles,
    result_overlay,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.sample_replays import (
    sample_result,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    TERMS,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.backtest.sandbox_fixtures import (
    bot,
)


def test_the_chart_draws_the_replayed_candles_as_they_were_replayed() -> None:
    outcome = outcome_of(sample_result())

    candles = chart_candles(outcome, "BTCUSDT", TimeFrame.FIFTEEN_MINUTES)

    assert [c.open_time for c in candles] == [b.time for b in outcome.bars]
    assert [c.open_price for c in candles] == [float(b.open) for b in outcome.bars]
    assert [c.close_price for c in candles] == [float(b.close) for b in outcome.bars]
    assert {c.interval for c in candles} == {"15m"}


def test_the_overlay_marks_each_replayed_fill_on_the_side_it_was_filled() -> None:
    outcome = outcome_of(sample_result())
    plan = SandboxPlan.from_bot(bot())

    overlay = result_overlay(GridKind(None, GridThresholds()), plan, TERMS, outcome)  # type: ignore[arg-type]

    assert len(overlay.fills) == len(outcome.fills) > 0
    assert {fill.side for fill in outcome.fills} == {OrderSide.BUY, OrderSide.SELL}
    for drawn, replayed in zip(overlay.fills, outcome.fills, strict=True):
        assert drawn.side is (
            FillSide.BUY if replayed.side is OrderSide.BUY else FillSide.SELL
        )
        assert (drawn.time, drawn.price, drawn.label) == (
            replayed.time,
            replayed.price,
            replayed.label,
        )
    assert overlay.lines, "the kind's own overlay (the ladder) is drawn under the fills"
