"""`EPIC-029D` — the Backtest page's preview builds offline with a sample
result, its caveats among the figures."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_fill_rule import (
    FILL_RULE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.grid_backtest_view import (
    GridBacktestView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.preview import (
    build_preview,
)


def test_the_preview_shows_a_coarse_sample_result(qtbot) -> None:
    view = build_preview()
    qtbot.addWidget(view)

    assert isinstance(view, GridBacktestView)
    shown = view.summary_text()
    assert FILL_RULE in view.notes.text()
    assert shown["candles"] == "120"
    assert shown["coarse_candles"] != "0"
    view.shutdown()
