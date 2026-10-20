"""`EPIC-040D` — every state `EPIC-040A` pinned on the Grid's own page, run through the workbench with
the Grid registered as the one kind: the same words, the same commands on, from the real handlers.

@details The workbench names no kind; the Grid reaches it through `IBotKind.backtester()`. Each test
drives it the way a person does (`follow`, a click) and reads what the person reads. Where the Grid's
page left a status stale (`EPIC-040A`'s three findings), the workbench says the state's own words."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_fill_rule import (
    FILL_RULE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench_view import (
    BacktestWorkbenchView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.workbench_selection import (
    WorkbenchSelection,
)

from .workbench_fixtures import (
    WorkbenchWorld,
    build_workbench,
    selection,
)


@pytest.fixture
def world(qtbot: Any) -> Iterator[WorkbenchWorld]:
    built = build_workbench()
    qtbot.addWidget(built.workbench.page)
    yield built
    built.workbench.shutdown()


def _buttons(view: BacktestWorkbenchView) -> dict[str, bool]:
    """Each command the page offers, by its label: whether the person can click it now."""
    return {
        button.text(): button.isEnabled()
        for button in (
            view.run_button,
            view.cancel_button,
            view.sync_button,
            view.no_funding_button,
        )
        if button.isVisibleTo(view)
    }


def _run(world: WorkbenchWorld, qtbot: Any) -> None:
    qtbot.mouseClick(world.workbench.view.run_button, Qt.MouseButton.LeftButton)


@pytest.mark.parametrize(
    ("chosen", "reason"),
    [
        (WorkbenchSelection(), "Select a bot to backtest its parameters."),
        (
            selection(terms=False),
            "The market numbers for this symbol are still being read.",
        ),
    ],
    ids=["no bot", "no market numbers"],
)
def test_idle_says_why_run_is_off(
    world: WorkbenchWorld, chosen: WorkbenchSelection, reason: str
) -> None:
    view = world.workbench.view

    world.workbench.follow(chosen)

    assert not view.run_button.isEnabled()
    assert view.run_button.toolTip() == reason
    assert view.status.text() == reason
    assert _buttons(view) == {"Run backtest": False, "Cancel": False}
    assert view.summary_text() == {}


def test_a_ready_page_says_nothing_stale(world: WorkbenchWorld) -> None:
    """The Grid page kept "Select a bot…" once ready (`EPIC-040A`): the status follows the state."""
    view = world.workbench.view
    world.workbench.follow(WorkbenchSelection())
    assert view.status.text() == "Select a bot to backtest its parameters."

    world.workbench.follow(selection())

    assert view.run_button.isEnabled() and view.run_button.toolTip() == ""
    assert view.status.text() == ""
    assert _buttons(view) == {"Run backtest": True, "Cancel": False}


def test_a_run_offers_only_cancel_and_says_what_it_runs(
    world: WorkbenchWorld, qtbot: Any
) -> None:
    view = world.workbench.view
    world.workbench.follow(selection())

    _run(world, qtbot)

    assert view.status.text() == "Backtesting BTCUSDT on 15m…"
    assert _buttons(view) == {"Run backtest": False, "Cancel": True}
    world.pool.run_all()


def test_a_run_shows_the_replay_its_equity_every_figure_and_every_caveat(
    world: WorkbenchWorld, qtbot: Any
) -> None:
    view = world.workbench.view
    world.workbench.follow(selection())

    _run(world, qtbot)
    world.pool.run_all()

    figures = view.summary_text()
    assert view.status.text() == "Backtest done."
    assert _buttons(view) == {"Run backtest": True, "Cancel": False}
    assert FILL_RULE in view.notes.text()
    assert figures["candles"] == "96" and figures["cycles"]
    assert view.equity.point_count() == 96
    assert view.fills_model.rowCount() > 0
    query = world.dispatcher.queries[-1]
    assert query.kind_id == "grid"
    assert (query.request.symbol, query.request.interval) == (
        "BTCUSDT",
        TimeFrame.FIFTEEN_MINUTES,
    )


def test_a_period_with_no_candles_offers_a_sync_and_only_a_click_syncs(
    qtbot: Any,
) -> None:
    world = build_workbench(stored=False, storing_sync=True)
    view = world.workbench.view
    qtbot.addWidget(view)
    world.workbench.follow(selection())

    _run(world, qtbot)
    world.pool.run_all()

    assert "No 15m candles of BTCUSDT" in view.status.text()
    assert _buttons(view) == {
        "Run backtest": True,
        "Cancel": False,
        "Sync candles": True,
    }
    assert world.sync.requests == []

    qtbot.mouseClick(view.sync_button, Qt.MouseButton.LeftButton)

    assert view.status.text().startswith("Syncing BTCUSDT 15m candles and 1-second")
    assert _buttons(view) == {"Run backtest": False, "Stop": True}
    world.pool.run_all()
    assert [request.interval for request in world.sync.requests] == [
        TimeFrame.FIFTEEN_MINUTES,
        TimeFrame.ONE_SECOND,
    ]
    assert {request.market for request in world.sync.requests} == {MarketType.SPOT}
    assert view.status.text() == "Backtest done."
    assert view.summary_text()["candles"] == "96"
    world.workbench.shutdown()


def test_stop_during_a_sync_says_what_it_stored_stays(qtbot: Any) -> None:
    world = build_workbench(stored=False, storing_sync=True)
    view = world.workbench.view
    qtbot.addWidget(view)
    world.workbench.follow(selection())
    _run(world, qtbot)
    world.pool.run_all()
    qtbot.mouseClick(view.sync_button, Qt.MouseButton.LeftButton)

    qtbot.mouseClick(view.cancel_button, Qt.MouseButton.LeftButton)
    world.pool.run_all()

    assert view.status.text() == "Sync stopped; what it already stored stays."
    assert world.sync.requests == [] and len(world.dispatcher.queries) == 1
    assert _buttons(view) == {"Run backtest": True, "Cancel": False}
    world.workbench.shutdown()


def test_the_sync_offer_survives_the_same_bot_being_re_read(qtbot: Any) -> None:
    """The Bots screen re-follows the selection on its clock and every planner answer."""
    world = build_workbench(stored=False)
    view = world.workbench.view
    qtbot.addWidget(view)
    world.workbench.follow(selection())
    _run(world, qtbot)
    world.pool.run_all()

    world.workbench.follow(selection())
    world.workbench.follow(selection())

    assert view.sync_button.isVisibleTo(view)
    assert "No 15m candles of BTCUSDT" in view.status.text()
    world.workbench.shutdown()


def test_a_period_partly_stored_is_replayed_and_says_what_is_missing(
    qtbot: Any,
) -> None:
    world = build_workbench(stored=False)
    from .workbench_fixtures import swinging_candles

    world.repository.save_klines(MarketType.SPOT, swinging_candles()[:48])
    view = world.workbench.view
    qtbot.addWidget(view)
    world.workbench.follow(selection())

    _run(world, qtbot)
    world.pool.run_all()

    assert view.summary_text()["stored_candles"] == "48"
    assert "not the whole period" in view.notes.text()
    assert "48 candles of the period are not stored" in view.status.text()
    assert view.sync_button.isVisibleTo(view)
    world.workbench.shutdown()
