"""`BOT-209` — the Plan dock as a person meets it: four frames of the real screen.

The frames are filled with the real planner's verdicts and the Futures rules' own words
(`plan_dock_frames.py`), so what a test reads is what the owner sees. Each rule the task states is
one test: the blocker is in the banner, a check's long text is never a second line of the dock, the
hint under a field is the list's own headline, and nothing overlaps or is cut at the three window
sizes the workbench suite uses.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QLabel, QScrollArea
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import BotsView
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_checks_view import (
    HEADING,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_dock_frames import (
    FRAMES,
    build_frame,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.notice_bar import NoticeKind

_SIZES = [(1024, 700), (1366, 768), (1920, 1080)]
_THIN_REASON_START = "The thinnest grid step is"


def _open(qtbot, name: str, size: tuple[int, int] = (1366, 768)) -> BotsView:
    view = build_frame(name, size)
    assert isinstance(view, BotsView)
    qtbot.addWidget(view)
    view.show()
    qtbot.waitExposed(view)
    return view


def _plan_labels(view: BotsView) -> list[str]:
    """Every text a label of the Plan dock shows now."""
    return [
        label.text()
        for label in view.plan.findChildren(QLabel)
        if label.isVisibleTo(view.plan) and label.text()
    ]


def test_the_four_frames_exist() -> None:
    assert set(FRAMES) == {
        "blocked_by_held_position",
        "thin_step_warning",
        "ready_draft",
        "running_bot",
    }


def test_the_blocker_is_in_the_banner_once_and_the_old_texts_are_gone(qtbot) -> None:
    view = _open(qtbot, "blocked_by_held_position")
    plan = view.plan

    assert plan.banner.isVisible() and plan.banner.kind is NoticeKind.CRITICAL
    assert plan.banner.text.startswith(
        "Run: ETHUSDT already holds a long position of 0.308"
    )
    assert "Last run: L14 SELL: the request failed" in plan.banner.text
    shown = " ".join(_plan_labels(view))
    assert shown.count("already holds a long position") == 1
    assert "Start: " not in shown
    assert "What the kind says about these parameters" not in shown
    # The state is the word; its note moved to the banner.
    assert plan.state.text() == "Draft"
    assert "L14 SELL" not in plan.state.text()
    # The banner is the first thing under the name, above the editor and the lists.
    top = plan.banner.mapTo(plan, plan.banner.rect().topLeft()).y()
    assert top < plan.checks.body.mapTo(plan, plan.checks.body.rect().topLeft()).y()
    assert (
        top
        < plan.properties.body.mapTo(plan, plan.properties.body.rect().topLeft()).y()
    )


def test_a_thin_step_is_one_headline_under_grids_and_in_the_list_never_a_paragraph(
    qtbot,
) -> None:
    view = _open(qtbot, "thin_step_warning")
    plan, panel = view.plan, view._kind_panel
    assert panel is not None

    row = next(
        (title, finding)
        for title, finding in plan.checks.rows()
        if title == "Grid step room for slippage"
    )
    hint = panel.field_error_text("grid_count")

    assert row[1].startswith("Step ") and "is thin" in row[1]
    assert hint == f"Advice: {row[1]}"
    # One source: the paragraph is the tooltip of the row and of the field, on no label at all.
    assert not any(_THIN_REASON_START in text for text in _plan_labels(view))
    assert _THIN_REASON_START in plan.checks.tooltip_of("Grid step room for slippage")
    assert _THIN_REASON_START in panel.grid_count.toolTip()
    assert plan.banner.text == "Ready to start"


def test_the_hints_button_proposes_the_count_that_clears_it_and_clicking_types_it(
    qtbot,
) -> None:
    view = _open(qtbot, "thin_step_warning")
    panel = view._kind_panel
    assert panel is not None
    button = panel.use_suggested_grids

    assert button.isVisible()
    count = int(button.text().split()[1])
    assert button.text() == f"Use {count} grids" and count < panel.grid_count.value()

    with qtbot.waitSignal(panel.config_changed):
        button.click()

    assert panel.grid_count.value() == count
    assert panel.config()["grid_count"] == str(count)


def test_a_plan_with_nothing_to_say_shows_no_button_and_one_folded_row(qtbot) -> None:
    view = _open(qtbot, "ready_draft")
    panel = view._kind_panel
    assert panel is not None

    assert view.plan.banner.text == "Ready to start"
    assert not panel.use_suggested_grids.isVisible()
    rows = view.plan.checks.rows()
    assert rows[0][0] == HEADING
    assert rows[-1][0].endswith("checks passed") or rows[-1][0].endswith("check passed")


def test_a_running_bot_has_no_banner_and_still_lists_its_checks_last(qtbot) -> None:
    view = _open(qtbot, "running_bot")
    plan = view.plan

    assert plan.banner.isHidden()
    assert plan.index_of_figures() < plan.index_of_parameters()
    assert plan._column.indexOf(plan.checks.body) > plan.index_of_parameters()


@pytest.mark.parametrize("size", _SIZES, ids=lambda size: f"{size[0]}x{size[1]}")
@pytest.mark.parametrize("name", sorted(FRAMES))
def test_nothing_overlaps_or_is_cut_at_the_three_window_sizes(
    qtbot, name: str, size: tuple[int, int]
) -> None:
    view = _open(qtbot, name, size)
    plan = view.plan
    table, checks = plan.properties.view, plan.checks.view
    for widget in (table, checks):
        if widget.isVisibleTo(plan):
            qtbot.waitUntil(lambda w=widget: w.height() >= w.sizeHint().height() - 2)
    scroll = plan.findChild(QScrollArea, "scrollBotPlan")
    assert scroll is not None
    content = scroll.widget()

    rects = {
        widget.objectName() or type(widget).__name__: QRect(
            widget.mapTo(content, widget.rect().topLeft()), widget.size()
        )
        for widget in (plan.banner, view._kind_panel, checks, table)
        if widget is not None and widget.isVisibleTo(plan)
    }
    names = list(rects)
    overlapping = [
        (a, b)
        for index, a in enumerate(names)
        for b in names[index + 1 :]
        if rects[a].intersects(rects[b])
    ]

    assert overlapping == []
    # The table's last row is inside the table, not cut where the next widget begins.
    last = plan.properties._proxy_index("last_price", 0)
    assert table.visualRect(last).bottom() <= table.viewport().height()
    if checks.isVisibleTo(plan):
        last_check = checks.model().index(0, 0)
        assert last_check.isValid()
        assert checks.visualRect(last_check).bottom() <= checks.viewport().height()
