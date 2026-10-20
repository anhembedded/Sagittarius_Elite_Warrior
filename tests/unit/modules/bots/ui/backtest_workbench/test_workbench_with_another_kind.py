"""`EPIC-040D` — the workbench draws a second kind's outcome with no Grid in the process.

@details A stub strategy kind registers a backtester (`EPIC-040B`'s stub shape) and a bare editor; the
workbench follows a bot of that kind, runs it through `RunBacktestQuery` and shows the figures, the
notes and the fills the stub answered. Nothing the page reads names a ladder."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from typing import Any

from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_kind_backtester import (
    IKindBacktester,
    KindBacktestRequest,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_answer import (
    BacktestAnswer,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_outcome import (
    BacktestBar,
    BacktestFigure,
    BacktestFill,
    BacktestOutcome,
    BacktestProvenance,
    EquityPoint,
    FigureKind,
    StopCause,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import BotOverlay
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.workbench_selection import (
    WorkbenchSelection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_kind_panel import (
    BotKindPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.plan.plan_world import (
    StubKind,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.backtest.sandbox_fixtures import (
    bot,
    market,
)

from .workbench_fixtures import build_workbench

_KIND = "strategy"


class _Backtester(IKindBacktester):
    def run(self, request: KindBacktestRequest) -> BacktestAnswer:
        bars = tuple(
            BacktestBar(
                request.start + timedelta(hours=n),
                Decimal(100 + n),
                Decimal(102 + n),
                Decimal(99 + n),
                Decimal(101 + n),
            )
            for n in range(3)
        )
        return BacktestOutcome(
            provenance=BacktestProvenance(
                tuple(request.config.items()),
                Decimal("0.001"),
                Decimal("0.001"),
                bars[0].time,
                bars[-1].time,
                "a signal acts on the next candle's open",
            ),
            bars=bars,
            equity=tuple(
                EquityPoint(b.time, Decimal(1000 + 10 * n), Decimal(1000 + n))
                for n, b in enumerate(bars)
            ),
            fills=(
                BacktestFill(
                    bars[0].time,
                    OrderSide.BUY,
                    Decimal(100),
                    Decimal(1),
                    Decimal("0.1"),
                    "Enter long",
                    False,
                ),
            ),
            stop=StopCause.END_OF_DATA,
            stop_detail="",
            maker_fees=Decimal(0),
            taker_fees=Decimal("0.1"),
            figures=(BacktestFigure("trades", "Trades", FigureKind.QUANTITY, 1),),
            notes=("Warm-up candles are replayed but never traded.",),
            detail=None,
        )


class _Strategy(StubKind):
    def __init__(self) -> None:
        super().__init__(_KIND)

    def validate(self, inputs: BotKindInputs) -> tuple[Verdict, ...]:
        return ()

    def overlay(self, inputs: BotKindInputs) -> BotOverlay:
        return BotOverlay()

    def backtester(self) -> IKindBacktester:
        return _Backtester()


class _Editor(BotKindPanel):
    def __init__(self) -> None:
        super().__init__()
        self._config: dict[str, str] = {}

    def set_config(self, config: Mapping[str, str]) -> None:
        self._config = dict(config)

    def config(self) -> dict[str, str]:
        return self._config

    def set_planner_market(self, market: PlannerMarket | None) -> None:
        return None

    def set_editable(self, editable: bool) -> None:
        return None


def test_a_strategy_bot_runs_and_its_figures_notes_and_fills_are_shown(
    qtbot: Any,
) -> None:
    world = build_workbench(kinds=[_Strategy()], editors=lambda _kind_id: _Editor())
    view = world.workbench.view
    qtbot.addWidget(view)
    strategy_bot = replace(bot("s00001", {"strategy": "ema_cross"}), kind=_KIND)
    world.workbench.follow(WorkbenchSelection(strategy_bot, market()))

    qtbot.mouseClick(view.run_button, Qt.MouseButton.LeftButton)
    world.pool.run_all()

    assert view.status.text() == "Backtest done."
    assert view.summary_text() == {"trades": "1"}
    assert "Warm-up candles" in view.notes.text()
    assert view.fills_model.rowCount() == 1
    assert view.equity.point_count() == 3
    assert world.dispatcher.queries[-1].kind_id == _KIND
    assert world.dispatcher.queries[-1].request.config == {"strategy": "ema_cross"}
    world.workbench.shutdown()
