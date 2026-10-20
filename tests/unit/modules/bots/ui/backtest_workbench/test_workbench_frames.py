"""`EPIC-040D` — the Grid-on-the-workbench frames the owner looks at: every state has one, each builds,
and the states the Grid's own page pinned in `EPIC-040A` read the same words in the frame as they did on
that page, which `EPIC-040F` deleted."""

from __future__ import annotations

from typing import Any

import pytest
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QScrollArea, QTabWidget
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.workbench_frames import (
    FRAMES,
    build_frame,
)

_CONTAINS = {
    "refused_funding": "A Futures backtest without funding flatters a leveraged grid",
}
_NOTES = {
    "futures_liquidated": ("Stopped by a liquidation", "forfeited"),
}
#: The page sits in the Bots centre between its docks, which leave a 1024-wide window less than
#: 700 px; the page asks for less (`EPIC-040E`).
_PAGE_WIDTH_ROOM = 640
_WORDS = {
    "idle_no_bot": "Select a bot to backtest its parameters.",
    "idle_no_market_numbers": "The market numbers for this symbol are still being read.",
    "running": "Backtesting BTCUSDT on 1h…",
    "spot_result": "Backtest done.",
    "futures_result": "Backtest done.",
    "cancelled": "Backtest cancelled; the last result stays.",
    "edits_question": "Answer the question above first.",
}


#: The thirteen states the Grid's own page had a frame for (`EPIC-040A`); the workbench keeps every one.
_STATES_THE_GRID_PAGE_HAD = {
    "idle_no_bot",
    "idle_no_market_numbers",
    "idle_ready",
    "running",
    "syncing",
    "refused_candles",
    "refused_funding",
    "spot_result",
    "futures_result",
    "futures_liquidated",
    "cancelled",
    "another_bot",
    "another_bot_mid_run",
}


def test_every_state_the_grid_page_had_is_a_workbench_frame_too() -> None:
    assert set(FRAMES) >= _STATES_THE_GRID_PAGE_HAD
    assert {"edited", "edits_question"} <= set(FRAMES)


@pytest.mark.parametrize("name", sorted(FRAMES))
def test_a_frame_builds_and_fits_the_smallest_window(qtbot: Any, name: str) -> None:
    view = build_frame(name)
    qtbot.addWidget(view)

    view.show()

    minimum = view.minimumSizeHint()
    assert minimum.width() <= _PAGE_WIDTH_ROOM, QSize(minimum)
    assert minimum.height() <= 700, QSize(minimum)
    view.shutdown()


@pytest.mark.parametrize(("name", "words"), sorted(_WORDS.items()))
def test_a_frame_says_the_states_own_words(qtbot: Any, name: str, words: str) -> None:
    view = build_frame(name)
    qtbot.addWidget(view)

    assert (
        view.status.text().replace("15m", "1h") == words or view.status.text() == words
    )
    view.shutdown()


@pytest.mark.parametrize(("name", "words"), sorted(_CONTAINS.items()))
def test_a_refusal_frame_says_the_applications_own_sentence(
    qtbot: Any, name: str, words: str
) -> None:
    view = build_frame(name)
    qtbot.addWidget(view)

    assert words in view.status.text()
    view.shutdown()


@pytest.mark.parametrize(("name", "words"), sorted(_NOTES.items()))
def test_a_liquidated_result_names_the_liquidation_and_the_margin_lost(
    qtbot: Any, name: str, words: tuple[str, ...]
) -> None:
    view = build_frame(name)
    qtbot.addWidget(view)

    for word in words:
        assert word in view.notes.text()
    view.shutdown()


def test_the_figures_tab_shows_its_figures_whole_beside_a_wide_chart(
    qtbot: Any,
) -> None:
    """Review of PR #378, the Grid page's test before `EPIC-040F`: the chart took every pixel the
    splitter had to give, leaving the figures a strip about 70 px wide at 1920 px, labels cut and no
    value visible. The Figures pane is at least as wide as its read-out."""
    view = build_frame("spot_result")
    qtbot.addWidget(view)
    view.resize(1920, 1000)
    view.show()
    qtbot.waitExposed(view)
    tabs = view.findChild(QTabWidget, "tabBacktestResults")
    assert tabs is not None
    tabs.setCurrentIndex(
        next(i for i in range(tabs.count()) if tabs.tabText(i) == "Figures")
    )

    pane = tabs.currentWidget()
    assert isinstance(pane, QScrollArea)
    assert pane.viewport().width() >= view.summary.sizeHint().width()
    view.shutdown()
