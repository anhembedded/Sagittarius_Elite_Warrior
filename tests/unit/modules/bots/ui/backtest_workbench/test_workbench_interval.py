"""`EPIC-040` follow-up — the workbench's interval is chosen like a chart's timeframe.

@details The owner found the interval drop-down out of date beside the charts' own picker: the pinned
timeframes as actions and "More timeframes…" with its grouped dialog. The workbench reuses that
component (`ChartToolbar`), limited to the intervals a backtest replays (`INTERVALS`)."""

from __future__ import annotations

from typing import Any

import pytest
from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench import (
    BacktestWorkbench,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench_view import (
    DEFAULT_INTERVAL,
    INTERVALS,
)

from .workbench_fixtures import WorkbenchWorld, build_workbench, selection

_CODES = [interval.value for interval in INTERVALS]


@pytest.fixture
def world(qtbot: Any) -> Any:
    built = build_workbench()
    qtbot.addWidget(built.workbench.page)
    yield built
    built.workbench.shutdown()


def _action_texts(workbench: BacktestWorkbench) -> list[str]:
    toolbar = workbench.view.interval
    return [action.text() for action in toolbar.timeframes.timeframe_actions()]


def test_it_opens_on_the_default_interval_with_each_replayed_interval_pinned(
    world: WorkbenchWorld,
) -> None:
    view = world.workbench.view

    assert view.chosen_interval() is DEFAULT_INTERVAL
    assert _action_texts(world.workbench) == _CODES
    checked = [
        action.text()
        for action in view.interval.timeframes.timeframe_actions()
        if action.isChecked()
    ]
    assert checked == [DEFAULT_INTERVAL.value]


def test_the_full_picker_offers_only_the_intervals_a_backtest_replays(
    world: WorkbenchWorld,
) -> None:
    toolbar = world.workbench.view.interval

    offered = {row.code for group in toolbar._selection.groups for row in group.rows}
    toolbar._selection.choose("1d")

    assert offered == set(_CODES)
    assert world.workbench.view.chosen_interval() is DEFAULT_INTERVAL


def test_choosing_an_interval_is_what_the_next_run_replays(
    world: WorkbenchWorld, qtbot: Any
) -> None:
    view = world.workbench.view
    world.workbench.follow(selection())
    action = view.interval.timeframes.action_for("1h")
    assert action is not None

    action.trigger()
    qtbot.mouseClick(view.run_button, Qt.MouseButton.LeftButton)
    world.pool.run_all()

    assert view.chosen_interval() is TimeFrame.ONE_HOUR
    assert world.dispatcher.queries[0].request.interval is TimeFrame.ONE_HOUR
