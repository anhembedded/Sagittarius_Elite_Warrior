"""`EPIC-029D` — the Grid Backtest page: Run shows the replay beside the bot it
was run for; Cancel and another bot drop a run in flight, so nothing it
computes is shown; a period with no candles offers a sync, and only a click
syncs, then runs again (`BUG-107`)."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_fill_rule import (
    FILL_RULE,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import ReadoutForm

from .grid_backtest_fixtures import (
    SYMBOL,
    BacktestWorld,
    build_backtest,
    context,
    swinging_candles,
)


@pytest.fixture
def world(qtbot: Any) -> Iterator[BacktestWorld]:
    built = build_backtest()
    qtbot.addWidget(built.backtest.page)
    yield built
    built.backtest.shutdown()


def _run(world: BacktestWorld, qtbot: Any) -> None:
    qtbot.mouseClick(world.backtest.view.run_button, Qt.MouseButton.LeftButton)


def test_without_a_bot_or_its_market_numbers_run_says_why_it_is_off(
    world: BacktestWorld,
) -> None:
    view = world.backtest.view
    assert not view.run_button.isEnabled()
    assert "Select a bot" in view.run_button.toolTip()

    world.backtest.follow(context(terms=False))

    assert not view.run_button.isEnabled()
    assert "market numbers" in view.run_button.toolTip()

    world.backtest.follow(context())

    assert view.run_button.isEnabled()


def test_run_shows_the_replay_its_equity_and_every_caveat(
    world: BacktestWorld, qtbot: Any
) -> None:
    view = world.backtest.view
    world.backtest.follow(context())

    _run(world, qtbot)

    assert not view.run_button.isEnabled()
    assert view.cancel_button.isEnabled()
    assert view.cancel_button.text() == "Cancel"
    world.pool.run_all()

    shown = view.summary_text()
    assert FILL_RULE in view.notes.text()
    assert shown["candles"] == "96"
    assert shown["cycles"]
    assert shown["coarse_candles"]
    assert isinstance(view.summary_form(), ReadoutForm)
    assert view.status.text() == "Backtest done."
    assert view.run_button.isEnabled() and not view.cancel_button.isEnabled()
    assert view.equity.grid_curve.getData()[0] is not None
    query = world.dispatcher.queries[-1]
    assert (query.symbol, query.interval) == (SYMBOL, TimeFrame.FIFTEEN_MINUTES)


def test_a_runs_figures_scroll_in_their_pane_and_never_raise_the_floor(
    world: BacktestWorld, qtbot: Any
) -> None:
    """The PR #361 review: the figures' dozen form rows set the page's
    minimum height, and with it the Bots mode's (554 px with a result). They
    scroll in their own pane, so a result never raises the page's floor."""
    view = world.backtest.view
    world.backtest.follow(context())
    view.show()
    qtbot.waitExposed(view)
    empty_floor = view.minimumSizeHint().height()

    _run(world, qtbot)
    world.pool.run_all()
    QCoreApplication.processEvents()  # the posted layout requests

    assert view.summary_text()
    assert view.minimumSizeHint().height() <= empty_floor


@pytest.mark.parametrize("finished_anyway", [False, True])
def test_cancel_publishes_nothing_and_the_last_result_stays(
    world: BacktestWorld, qtbot: Any, finished_anyway: bool
) -> None:
    view = world.backtest.view
    world.dispatcher.honours_cancel = not finished_anyway
    world.backtest.follow(context())
    _run(world, qtbot)
    world.pool.run_all()
    before = view.summary_text()

    _run(world, qtbot)
    qtbot.mouseClick(view.cancel_button, Qt.MouseButton.LeftButton)
    world.pool.run_all()

    assert view.summary_text() == before
    assert view.status.text() == "Backtest cancelled; the last result stays."
    assert view.run_button.isEnabled()
    assert world.dispatcher.queries[-1].cancelled()


@pytest.mark.parametrize("finished_anyway", [False, True])
def test_another_bot_drops_the_run_in_flight_and_clears_the_result(
    world: BacktestWorld, qtbot: Any, finished_anyway: bool
) -> None:
    view = world.backtest.view
    world.dispatcher.honours_cancel = not finished_anyway
    world.backtest.follow(context("a3f9c1"))
    _run(world, qtbot)
    world.pool.run_all()
    assert view.summary_text()

    _run(world, qtbot)
    world.backtest.follow(context("b7e2d4"))
    world.pool.run_all()

    assert view.summary_text() == {}
    assert view.notes.text() == ""
    assert view.run_button.isEnabled()
    assert view.status.text() != "Backtest done."


def test_the_same_bot_re_read_keeps_its_run_and_result(
    world: BacktestWorld, qtbot: Any
) -> None:
    view = world.backtest.view
    world.backtest.follow(context())
    _run(world, qtbot)

    world.backtest.follow(context())
    world.pool.run_all()

    assert view.status.text() == "Backtest done."
    assert view.summary_text()


def test_a_period_with_no_candles_offers_a_sync_and_only_a_click_syncs(
    qtbot: Any,
) -> None:
    world = build_backtest(stored=False, storing_sync=True)
    view = world.backtest.view
    qtbot.addWidget(view)
    world.backtest.follow(context())

    _run(world, qtbot)
    world.pool.run_all()

    assert view.sync_button.isVisibleTo(view)
    assert "No 15m candles of BTCUSDT" in view.status.text()
    assert world.sync.requests == []

    qtbot.mouseClick(view.sync_button, Qt.MouseButton.LeftButton)

    assert view.cancel_button.text() == "Stop"
    assert not view.sync_button.isVisibleTo(view)
    world.pool.run_all()

    assert [request.interval for request in world.sync.requests] == [
        TimeFrame.FIFTEEN_MINUTES,
        TimeFrame.ONE_SECOND,
    ]
    assert view.status.text() == "Backtest done."
    assert view.summary_text()["candles"] == "96"
    world.backtest.shutdown()


def test_stop_during_a_sync_says_what_it_stored_stays(qtbot: Any) -> None:
    world = build_backtest(stored=False, storing_sync=True)
    view = world.backtest.view
    qtbot.addWidget(view)
    world.backtest.follow(context())
    _run(world, qtbot)
    world.pool.run_all()
    qtbot.mouseClick(view.sync_button, Qt.MouseButton.LeftButton)

    qtbot.mouseClick(view.cancel_button, Qt.MouseButton.LeftButton)
    world.pool.run_all()

    assert view.status.text() == "Sync stopped; what it already stored stays."
    assert world.sync.requests == []
    assert world.dispatcher.queries[-1].interval is TimeFrame.FIFTEEN_MINUTES
    assert len(world.dispatcher.queries) == 1
    world.backtest.shutdown()


def test_the_sync_offer_survives_the_same_bot_being_re_read(qtbot: Any) -> None:
    """The Bots screen re-follows the selection on its clock, every planner
    answer and every edit; none of that takes the offer away."""
    world = build_backtest(stored=False)
    view = world.backtest.view
    qtbot.addWidget(view)
    world.backtest.follow(context())
    _run(world, qtbot)
    world.pool.run_all()
    assert view.sync_button.isVisibleTo(view)

    world.backtest.follow(context())
    world.backtest.follow(context())

    assert view.sync_button.isVisibleTo(view)
    assert "No 15m candles of BTCUSDT" in view.status.text()
    world.backtest.shutdown()


def test_a_period_partly_stored_is_replayed_and_says_what_is_missing(
    qtbot: Any,
) -> None:
    world = build_backtest(stored=False)
    world.repository.save_klines(MarketType.SPOT, swinging_candles()[:48])
    view = world.backtest.view
    qtbot.addWidget(view)
    world.backtest.follow(context())

    _run(world, qtbot)
    world.pool.run_all()

    assert view.summary_text()["stored_candles"] == "48"
    assert view.summary_text()["expected_candles"] == "96"
    assert "not the whole period" in view.notes.text()
    assert "48 candles of the period are not stored" in view.status.text()
    assert view.sync_button.isVisibleTo(view)
    world.backtest.shutdown()


def test_closing_the_page_mid_run_drops_the_answer_without_an_error(
    qtbot: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """Deselecting a bot (or selecting another kind) closes the page while its
    run or sync is still on the pool; the worker's answer must find nothing
    to raise against when it lands."""
    world = build_backtest()
    view = world.backtest.view
    world.backtest.follow(context())
    _run(world, qtbot)

    world.backtest.shutdown()
    view.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    world.pool.run_all()

    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
