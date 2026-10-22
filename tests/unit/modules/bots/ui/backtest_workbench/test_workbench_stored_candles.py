"""`BOT-233` — the Backtest workbench shows the stored candles of its period before any run.

The owner (2026-10-22): opening Backtest showed an empty chart on the 1970 axis, with no way to load
candles, so the price history could not be seen while a grid was designed. The page now reads the
candles stored for the bot's own venue (`BUG-172`) for the chosen interval and period, needs no grid
parameters, offers Sync candles when some are not stored, and says in words when the period holds more
than one backtest draws.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from PySide6.QtCore import QDateTime, Qt, QTimeZone
from PySide6.QtWidgets import QLabel
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_stored_candles import (
    GetStoredCandlesQuery,
    StoredCandles,
)

from .workbench_candles import CANDLES, PERIOD, SYMBOL
from .workbench_fixtures import (
    WorkbenchWorld,
    build_workbench,
    selection,
)


def _drawn(world: WorkbenchWorld) -> int:
    return len(world.workbench.view.card._raw_history)


def _notice(world: WorkbenchWorld) -> QLabel:
    notice = world.workbench.view.card.findChild(QLabel, "lblChartNoCandles")
    assert notice is not None
    return notice


def _set_period(world: WorkbenchWorld, *, start: Any = None, end: Any = None) -> None:
    view = world.workbench.view
    utc = QTimeZone.utc()
    for edit, moment in ((view.start, start), (view.end, end)):
        if moment is not None:
            edit.setDateTime(QDateTime.fromSecsSinceEpoch(int(moment.timestamp()), utc))


def _follow_and_read(world: WorkbenchWorld) -> None:
    world.workbench.follow(selection())
    world.pool.run_all()


@pytest.fixture
def stored(qtbot: Any) -> Any:
    world = build_workbench()
    qtbot.addWidget(world.workbench.page)
    yield world
    world.workbench.shutdown()


def test_a_chart_with_no_bot_says_so_and_never_draws_the_1970_axis(
    qtbot: Any,
) -> None:
    world = build_workbench()
    qtbot.addWidget(world.workbench.page)

    assert not _notice(world).isHidden()
    assert "Select a bot" in _notice(world).text()
    assert world.workbench.view.card.plot_layout.widget.isHidden()
    world.workbench.shutdown()


def test_following_a_bot_draws_its_stored_candles_with_no_run_and_no_parameters(
    stored: WorkbenchWorld,
) -> None:
    _follow_and_read(stored)
    view = stored.workbench.view

    assert _drawn(stored) == CANDLES
    assert _notice(stored).isHidden()
    assert view.candles.text() == f"All {CANDLES} 15m candles of the period are stored."
    assert not view.sync_button.isVisibleTo(view)
    assert stored.dispatcher.queries == []


def test_changing_the_interval_reads_that_intervals_candles_and_offers_the_sync(
    stored: WorkbenchWorld,
) -> None:
    _follow_and_read(stored)
    view = stored.workbench.view

    action = view.interval.timeframes.action_for("1h")
    assert action is not None
    action.trigger()
    stored.pool.run_all()

    assert _drawn(stored) == 0
    assert (
        _notice(stored).text()
        == f"No 1h candles of {SYMBOL} are stored for this period. Sync candles fetches them."
    )
    assert view.sync_button.isVisibleTo(view)


def test_a_period_longer_than_what_is_stored_draws_it_and_offers_the_rest(
    stored: WorkbenchWorld,
) -> None:
    _follow_and_read(stored)
    view = stored.workbench.view

    _set_period(stored, end=PERIOD[1] + timedelta(hours=6))
    stored.pool.run_all()

    assert _drawn(stored) == CANDLES
    assert _notice(stored).isHidden()
    assert view.candles.text() == (
        f"{CANDLES} of the {CANDLES + 24} 15m candles of the period are stored. "
        "The rest are not stored; Sync candles fetches them."
    )
    assert view.sync_button.isVisibleTo(view)


def test_a_period_over_the_most_one_backtest_draws_names_the_remedy(
    stored: WorkbenchWorld,
) -> None:
    _follow_and_read(stored)
    view = stored.workbench.view

    _set_period(stored, start=PERIOD[1] - timedelta(days=300))
    stored.pool.run_all()

    text = view.candles.text()
    assert "candles is more than one backtest draws (20000)" in text
    assert "choose a shorter period or a larger interval" in text
    assert _notice(stored).text() == text
    assert not view.sync_button.isVisibleTo(view)


def test_sync_from_the_chart_stores_the_candles_and_draws_them_without_a_run(
    qtbot: Any,
) -> None:
    world = build_workbench(stored=False, storing_sync=True)
    qtbot.addWidget(world.workbench.page)
    view = world.workbench.view
    _follow_and_read(world)
    assert _drawn(world) == 0 and view.sync_button.isVisibleTo(view)

    qtbot.mouseClick(view.sync_button, Qt.MouseButton.LeftButton)
    world.pool.run_all()

    assert _drawn(world) == CANDLES
    assert not view.sync_button.isVisibleTo(view)
    assert world.dispatcher.queries == []
    assert {request.market for request in world.sync.requests} == {MarketType.SPOT}
    assert {request.interval for request in world.sync.requests} == {
        TimeFrame.FIFTEEN_MINUTES,
        TimeFrame.ONE_SECOND,
    }
    world.workbench.shutdown()


def test_a_result_keeps_the_chart_until_the_next_run(
    stored: WorkbenchWorld, qtbot: Any
) -> None:
    _follow_and_read(stored)
    view = stored.workbench.view
    qtbot.mouseClick(view.run_button, Qt.MouseButton.LeftButton)
    stored.pool.run_all()
    result = list(view.card._raw_history)

    action = view.interval.timeframes.action_for("1h")
    assert action is not None
    action.trigger()
    stored.pool.run_all()

    assert result and list(view.card._raw_history) == result
    assert _notice(stored).isHidden()


def test_an_answer_for_a_window_no_longer_asked_for_is_dropped(
    stored: WorkbenchWorld,
) -> None:
    stored.workbench.follow(selection())  # the 15m read is held, not yet run
    view = stored.workbench.view
    action = view.interval.timeframes.action_for("1h")
    assert action is not None
    action.trigger()  # asks for 1h; the 15m read is now stale

    stored.pool.run_all()

    assert _drawn(stored) == 0
    assert "No 1h candles" in view.candles.text()


def test_a_read_that_fails_is_told_once_in_words(qtbot: Any) -> None:
    def failing(query: GetStoredCandlesQuery) -> StoredCandles:
        raise OSError("disk unreadable")

    world = build_workbench(read_candles=failing)
    qtbot.addWidget(world.workbench.page)

    _follow_and_read(world)

    assert len(world.notifier.failures) == 1
    assert "stored candles could not be read" in world.notifier.failures[0].headline
    assert "could not be read" in world.workbench.view.candles.text()
    world.workbench.shutdown()
