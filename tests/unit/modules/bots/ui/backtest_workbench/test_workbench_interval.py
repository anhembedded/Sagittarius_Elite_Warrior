"""`EPIC-040` follow-up — the workbench's interval is chosen like a chart's timeframe.

@details The owner found the interval drop-down out of date beside the charts' own picker: the pinned
timeframes as actions and "More timeframes…" with its grouped dialog. The workbench reuses that
component (`ChartToolbar`), offering every interval the bot's market loads (`BOT-232`)."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench import (
    BacktestWorkbench,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.candle_window import (
    CandleWindow,
    sync_requests,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.interval_toolbar import (
    DEFAULT_INTERVAL,
    OFFERED_INTERVALS,
    PINNED_INTERVALS,
    UNREPLAYED_INTERVALS,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .workbench_candles import PERIOD
from .workbench_fixtures import (
    WorkbenchWorld,
    build_workbench,
    futures_selection,
    selection,
)

_CODES = [interval.value for interval in PINNED_INTERVALS]
_EVERY_CODE = {interval.value for interval in OFFERED_INTERVALS}


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


def _offered(workbench: BacktestWorkbench) -> set[str]:
    toolbar = workbench.view.interval
    return {row.code for group in toolbar._selection.groups for row in group.rows}


def test_the_full_picker_offers_every_interval_the_replay_judges_in_the_charts_groups(
    world: WorkbenchWorld,
) -> None:
    toolbar = world.workbench.view.interval

    toolbar._selection.choose("1d")
    groups = [
        (group.label, [row.code for row in group.rows])
        for group in toolbar._selection.groups
    ]

    assert _offered(world.workbench) == _EVERY_CODE
    assert [label for label, _ in groups] == [
        "SECONDS",
        "MINUTES",
        "HOURS",
        "DAYS AND UP",
    ]
    assert world.workbench.view.chosen_interval() is TimeFrame.ONE_DAY
    assert _action_texts(world.workbench)[:4] == _CODES


def test_the_full_picker_warns_that_seconds_are_heavy(world: WorkbenchWorld) -> None:
    assert world.workbench.view.interval._selection.has_warning


def test_a_futures_bot_is_not_offered_1s_which_futures_serves_no_klines_for(
    world: WorkbenchWorld,
) -> None:
    world.workbench.follow(futures_selection())

    assert _offered(world.workbench) == _EVERY_CODE - {"1s"}


def test_a_chosen_1s_moves_to_1m_when_the_bot_followed_is_a_futures_one(
    world: WorkbenchWorld,
) -> None:
    world.workbench.follow(selection())
    world.workbench.view.interval._selection.choose("1s")
    assert world.workbench.view.chosen_interval() is TimeFrame.ONE_SECOND

    world.workbench.follow(futures_selection())

    assert world.workbench.view.chosen_interval() is TimeFrame.ONE_MINUTE


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


def _reachable_by_tab(workbench: BacktestWorkbench) -> list[str]:
    toolbar = workbench.view.interval
    actions = [*toolbar.timeframes.timeframe_actions(), toolbar.timeframes.more_action]
    return [
        action.text()
        for action in actions
        if (button := toolbar.widgetForAction(action)) is not None
        and button.focusPolicy() & Qt.FocusPolicy.TabFocus
    ]


def test_every_interval_button_is_reachable_by_the_tab_key(
    world: WorkbenchWorld,
) -> None:
    """The drop-down this replaced was in the tab order; a toolbar's buttons are not by default."""
    assert _reachable_by_tab(world.workbench) == [*_CODES, "More timeframes…"]


def test_a_button_made_by_re_pinning_is_reachable_by_the_tab_key_too(
    world: WorkbenchWorld,
) -> None:
    toolbar = world.workbench.view.interval
    toolbar._selection.toggle_pinned("5m")
    toolbar._selection.toggle_pinned("5m")

    assert _reachable_by_tab(world.workbench) == [*_CODES, "More timeframes…"]


def test_the_result_chart_has_no_timeframe_row_of_its_own(
    world: WorkbenchWorld,
) -> None:
    """`EPIC-040` F3: the replay is at the interval that was run; a second chooser beside the
    picker would change nothing the person ran, and offered `1d`."""
    card = world.workbench.view.card
    timeframes = card.toolbar.timeframes

    visible = [
        action
        for action in (*timeframes.timeframe_actions(), timeframes.more_action)
        if action.isVisible()
    ]

    assert visible == []


def test_the_row_always_shows_the_interval_run_replays(world: WorkbenchWorld) -> None:
    """`EPIC-040` F4: every other pin can go, the chosen one cannot, and choosing pins."""
    view = world.workbench.view
    toolbar = view.interval
    for code in _CODES:
        toolbar._selection.toggle_pinned(code)

    chosen = view.chosen_interval().value
    assert [a.text() for a in toolbar.timeframes.timeframe_actions()] == [chosen]
    assert [
        a.text() for a in toolbar.timeframes.timeframe_actions() if a.isChecked()
    ] == [chosen]

    toolbar._selection.choose("1h")  # not pinned any more: choosing pins it

    assert view.chosen_interval() is TimeFrame.ONE_HOUR
    checked = [
        a.text() for a in toolbar.timeframes.timeframe_actions() if a.isChecked()
    ]
    assert checked == ["1h"]


def test_the_intervals_whose_candles_are_off_the_epoch_grid_are_not_offered() -> None:
    """Review of `BOT-232`: 3d, 1w and 1M candles open off the grid the replay counts and windows by,
    so a stored period would read "partly stored" for ever. The set is locked; widening the picker to
    them needs the calendar-aware replay (`UNREPLAYED_INTERVALS`)."""
    assert {
        TimeFrame.THREE_DAYS,
        TimeFrame.ONE_WEEK,
        TimeFrame.ONE_MONTH,
    } == UNREPLAYED_INTERVALS
    assert set(OFFERED_INTERVALS) == set(TimeFrame) - UNREPLAYED_INTERVALS


def test_the_picker_does_not_list_them(world: WorkbenchWorld) -> None:
    assert not {"3d", "1w", "1M"} & _offered(world.workbench)


def test_a_1s_sync_asks_for_the_1s_series_once() -> None:
    request = CandleWindow(
        "BTCUSDT",
        TradingVenue.SPOT_TESTNET,
        TimeFrame.ONE_SECOND,
        PERIOD[0],
        PERIOD[1],
    )

    asked = [r.interval for r in sync_requests(request)]

    assert asked == [TimeFrame.ONE_SECOND]
    other = [
        r.interval for r in sync_requests(replace(request, interval=TimeFrame.ONE_HOUR))
    ]
    assert other == [TimeFrame.ONE_HOUR, TimeFrame.ONE_SECOND]
