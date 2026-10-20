"""`EPIC-040F` — what the workbench does in the market of the bot's venue: a Spot run waits for no
leverage brackets, and a sync asks for the venue's own candles (`BUG-172`). Both were the Grid page's
tests before the page went (`EPIC-040A`)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_answer import (
    BacktestRefusal,
)

from .workbench_fixtures import build_workbench, futures_selection, selection


def test_a_spot_run_does_not_wait_for_brackets(qtbot: Any) -> None:
    world = build_workbench()
    qtbot.addWidget(world.workbench.page)

    world.workbench.follow(selection())

    assert world.workbench.view.run_button.isEnabled()
    world.workbench.shutdown()


def test_a_sync_asks_for_the_candles_of_the_venues_market(qtbot: Any) -> None:
    world = build_workbench(
        answers=(BacktestRefusal("No 15m candles stored.", missing_candles=True),)
    )
    view = world.workbench.view
    qtbot.addWidget(world.workbench.page)
    world.workbench.follow(futures_selection())
    qtbot.mouseClick(view.run_button, Qt.MouseButton.LeftButton)
    world.pool.run_all()

    qtbot.mouseClick(view.sync_button, Qt.MouseButton.LeftButton)
    world.pool.run_all()

    assert world.sync.requests
    assert {request.market for request in world.sync.requests} == {
        MarketType.FUTURES_USD_M
    }
    world.workbench.shutdown()
