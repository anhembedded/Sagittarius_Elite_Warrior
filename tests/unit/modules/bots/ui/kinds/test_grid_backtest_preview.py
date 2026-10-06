"""`EPIC-029D` — the Backtest page's preview builds offline with a sample
result, its caveats among the figures."""

from __future__ import annotations

from PySide6.QtWidgets import QScrollArea
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


def test_the_figures_pane_shows_its_figures_whole_beside_a_wide_chart(qtbot) -> None:
    """Review of PR #378: the equity chart took every pixel the splitter had
    to give, leaving the figures a strip about 70 px wide at 1920 px, labels
    cut and no value visible. The pane is at least as wide as its read-out."""
    view = build_preview()
    qtbot.addWidget(view)
    view.resize(1920, 1000)
    view.show()
    qtbot.waitExposed(view)
    form = view.summary_form()
    assert form is not None

    pane = view.findChild(QScrollArea, "scrollGridBacktestFigures")
    assert pane is not None
    assert pane.viewport().width() >= form.sizeHint().width()
    view.shutdown()
