"""`EPIC-043C`: the Plan dock's figures, banner and checks take the meaning table's tones.

What the dock says is in words and in arrows and signs; the colour only adds to it.
"""

from __future__ import annotations

import pytest
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QLabel, QStyleOptionViewItem
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_checks import (
    plan_checks_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_checks_view import (
    PlanChecksView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_property_grid import (
    VALUE_COLUMN,
    PlanPropertyGrid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_property_rows import (
    PROPERTY_GROUPS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_status import (
    PlanStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_status_banner import (
    PlanStatusBanner,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    Tone,
    tone_colour,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.notice_bar import NoticeKind

_TEXT = QPalette.ColorRole.Text
_WINDOW_TEXT = QPalette.ColorRole.WindowText


def _palette() -> QPalette:
    return QGuiApplication.palette()


def _grid(qtbot) -> PlanPropertyGrid:
    grid = PlanPropertyGrid(PROPERTY_GROUPS)
    qtbot.addWidget(grid.view)
    grid.view.resize(420, 600)
    grid.view.show()
    return grid


def _grid_colour(grid: PlanPropertyGrid, key: str) -> QColor:
    index = grid._proxy_index(key, VALUE_COLUMN)
    option = QStyleOptionViewItem()
    grid.view.itemDelegate().initStyleOption(option, index)
    return option.palette.color(_TEXT)


def test_a_figure_row_is_painted_in_the_tone_it_is_given(qtbot) -> None:
    grid = _grid(qtbot)

    grid.set_values(
        {"total_pnl": "▼ -3.00", "grid_profit": "▲ +12.50"},
        {"total_pnl": Tone.NEGATIVE, "grid_profit": Tone.POSITIVE},
    )

    assert _grid_colour(grid, "total_pnl") == tone_colour(Tone.NEGATIVE, _palette())
    assert _grid_colour(grid, "grid_profit") == tone_colour(Tone.POSITIVE, _palette())
    assert grid.shown_value("total_pnl") == "▼ -3.00"


def test_a_row_left_out_of_the_tones_loses_its_colour(qtbot) -> None:
    grid = _grid(qtbot)
    grid.set_values({"total_pnl": "▼ -3.00"}, {"total_pnl": Tone.NEGATIVE})
    plain = _grid_colour(grid, "symbol")

    grid.set_values({"total_pnl": "0.00"}, {})

    assert _grid_colour(grid, "total_pnl") == plain


def test_values_written_without_tones_keep_the_rows_tone(qtbot) -> None:
    grid = _grid(qtbot)
    grid.set_values({"total_pnl": "▼ -3.00"}, {"total_pnl": Tone.NEGATIVE})

    grid.set_values({"total_pnl": "▼ -4.00"})

    assert _grid_colour(grid, "total_pnl") == tone_colour(Tone.NEGATIVE, _palette())


def _banner_colour(banner: PlanStatusBanner) -> QColor:
    labels = [label for label in banner.findChildren(QLabel) if label.text()]
    assert len(labels) == 1
    return labels[0].palette().color(_WINDOW_TEXT)


@pytest.mark.parametrize(
    ("kind", "tone"),
    [
        (NoticeKind.CRITICAL, Tone.NEGATIVE),
        (NoticeKind.WARNING, Tone.CAUTION),
    ],
)
def test_the_banner_message_takes_the_tone_of_its_severity(
    qtbot, kind: NoticeKind, tone: Tone
) -> None:
    banner = PlanStatusBanner()
    qtbot.addWidget(banner)

    banner.show_status(PlanStatus(kind, "something to see"))

    assert _banner_colour(banner) == tone_colour(tone, _palette())


def test_ready_to_start_is_good_news_and_an_information_notice_is_plain(qtbot) -> None:
    banner = PlanStatusBanner()
    qtbot.addWidget(banner)

    banner.show_status(PlanStatus(NoticeKind.INFORMATION, "Connecting…"))
    plain = _banner_colour(banner)
    banner.show_status(
        PlanStatus(NoticeKind.INFORMATION, "Ready to start", Tone.POSITIVE)
    )

    assert _banner_colour(banner) == tone_colour(Tone.POSITIVE, _palette())
    assert plain == banner.palette().color(_WINDOW_TEXT)


def _v(severity: VerdictSeverity, title: str) -> Verdict:
    return Verdict(
        severity, title.upper(), f"{title} holds", title=title, summary=title
    )


def _check_colour(checks: PlanChecksView, title: str) -> QColor:
    found = [
        checks.model.indexFromItem(item)
        for item in _items(checks)
        if item.text() == title
    ]
    assert len(found) == 1
    option = QStyleOptionViewItem()
    checks.view.itemDelegate().initStyleOption(option, found[0])
    return option.palette.color(_TEXT)


def _items(checks: PlanChecksView):
    stack = [checks.model.invisibleRootItem()]
    while stack:
        item = stack.pop()
        yield from (item.child(r, 0) for r in range(item.rowCount()))
        stack.extend(item.child(r, 0) for r in range(item.rowCount()))


def test_a_check_is_painted_by_its_severity(qtbot) -> None:
    checks = PlanChecksView()
    qtbot.addWidget(checks.body)
    checks.body.resize(520, 300)
    checks.body.show()
    checks.show_checks(
        plan_checks_of(
            [
                _v(VerdictSeverity.REFUSED, "Capital"),
                _v(VerdictSeverity.WARNING, "Step"),
            ]
        )
    )

    assert _check_colour(checks, "Capital") == tone_colour(Tone.NEGATIVE, _palette())
    assert _check_colour(checks, "Step") == tone_colour(Tone.CAUTION, _palette())
