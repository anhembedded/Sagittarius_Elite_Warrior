"""`EPIC-040E` — the Bots centre's frames, which the owner looks at: each builds, shows the tab it
names, and the off tab keeps its place and says why."""

from __future__ import annotations

from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench_view import (
    BacktestWorkbenchView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    NO_BACKTEST_TEXT,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.centre_tab_frames import (
    FRAMES,
    build_frame,
)


@pytest.mark.parametrize("name", sorted(FRAMES))
def test_a_frame_builds_with_both_tabs(qtbot: Any, name: str) -> None:
    view = build_frame(name)
    qtbot.addWidget(view)

    assert [view.centre.tabText(i) for i in range(view.centre.count())] == [
        "Live",
        "Backtest",
    ]


def test_the_live_frame_shows_the_chart_and_the_backtest_frames_the_workbench(
    qtbot: Any,
) -> None:
    live = build_frame("live_tab")
    result = build_frame("backtest_tab_result")
    for view in (live, result):
        qtbot.addWidget(view)

    assert live.centre.currentIndex() == 0
    assert result.centre.currentIndex() == 1
    page = result.backtest.findChildren(BacktestWorkbenchView)[0]
    assert page.status.text() == "Backtest done."


def test_the_off_frame_keeps_the_tab_and_says_why(qtbot: Any) -> None:
    view = build_frame("backtest_tab_off")
    qtbot.addWidget(view)

    assert not view.centre.isTabEnabled(1) and view.centre.isTabVisible(1)
    assert view.centre.tabToolTip(1) == NO_BACKTEST_TEXT
    assert view.centre.currentIndex() == 0
