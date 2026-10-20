"""`EPIC-040F` — an answer that arrives after the person moved on is fenced off, whatever it holds.

@details The Grid page's tests ran each of these twice, once with a query that honours the cancel and
once with one that had already finished (`finished_anyway`). On the workbench the default dispatcher
runs the real handler, which honours it, so the answer that arrives is a `BacktestCancelled` and the
fence is never the only thing standing; here the dispatcher is scripted to answer with a full outcome
whatever was asked, so only the fence keeps it off the page."""

from __future__ import annotations

from typing import Any

import pytest
from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_kind_backtester import (
    outcome_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.sample_replays import (
    futures_result,
    sample_result,
)

from .workbench_fixtures import WorkbenchWorld, build_workbench, selection


@pytest.fixture
def world(qtbot: Any):  # type: ignore[no-untyped-def]
    built = build_workbench(
        answers=(outcome_of(sample_result()), outcome_of(futures_result()))
    )
    qtbot.addWidget(built.workbench.page)
    yield built
    built.workbench.shutdown()


def _run(world: WorkbenchWorld, qtbot: Any) -> None:
    qtbot.mouseClick(world.workbench.view.run_button, Qt.MouseButton.LeftButton)


def test_a_full_answer_that_ignored_cancel_does_not_replace_the_last_result(
    world: WorkbenchWorld, qtbot: Any
) -> None:
    view = world.workbench.view
    world.workbench.follow(selection())
    _run(world, qtbot)
    world.pool.run_all()
    before = view.summary_text()
    assert "funding_paid" not in before

    _run(world, qtbot)
    qtbot.mouseClick(view.cancel_button, Qt.MouseButton.LeftButton)
    world.pool.run_all()

    assert view.summary_text() == before
    assert view.status.text() == "Backtest cancelled; the last result stays."


def test_a_full_answer_for_the_bot_left_behind_shows_nothing(
    world: WorkbenchWorld, qtbot: Any
) -> None:
    view = world.workbench.view
    world.workbench.follow(selection("a3f9c1"))
    _run(world, qtbot)

    world.workbench.follow(selection("b7e2d4"))
    world.pool.run_all()

    assert view.summary_text() == {} and view.notes.text() == ""
    assert view.status.text() == ""
    assert view.run_button.isEnabled() and not view.cancel_button.isEnabled()
