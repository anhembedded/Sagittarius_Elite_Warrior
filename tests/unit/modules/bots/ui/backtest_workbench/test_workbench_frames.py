"""`EPIC-040D` — the Grid-on-the-workbench frames the owner looks at: every state has one, each builds,
and the states the page pinned in `EPIC-040A` read the same words in the frame as on the old page."""

from __future__ import annotations

from typing import Any

import pytest
from PySide6.QtCore import QSize
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.preview_frames import (
    FRAMES as GRID_PAGE_FRAMES,
)
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
_WORDS = {
    "idle_no_bot": "Select a bot to backtest its parameters.",
    "idle_no_market_numbers": "The market numbers for this symbol are still being read.",
    "running": "Backtesting BTCUSDT on 1h…",
    "spot_result": "Backtest done.",
    "futures_result": "Backtest done.",
    "cancelled": "Backtest cancelled; the last result stays.",
    "edits_question": "Answer the question above first.",
}


def test_every_state_the_grid_page_has_is_a_workbench_frame_too() -> None:
    assert set(GRID_PAGE_FRAMES) <= set(FRAMES)
    assert {"edited", "edits_question"} <= set(FRAMES)


@pytest.mark.parametrize("name", sorted(FRAMES))
def test_a_frame_builds_and_fits_the_smallest_window(qtbot: Any, name: str) -> None:
    view = build_frame(name)
    qtbot.addWidget(view)

    view.show()

    minimum = view.minimumSizeHint()
    assert minimum.width() <= 1024 and minimum.height() <= 700, QSize(minimum)
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
