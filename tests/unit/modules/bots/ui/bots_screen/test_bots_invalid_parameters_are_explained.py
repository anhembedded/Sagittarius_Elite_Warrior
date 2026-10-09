"""`EPIC-035N` (L10) — an invalid parameter is explained where it is.

The owner's screenshot: the refusal sat at the top of the Plan panel, the field it
is about was scrolled out of view below the figures, nothing on the field said it
was wrong, the chart was silent about the missing grid, and Save said "done" over a
plan Start would refuse. Now the parameters of a bot at rest come before its
figures, a field with a verdict carries a sign beside its sentence, the chart says
"Grid not drawn: …", and a Save names why Start is still blocked.

The status bar's line of the audit is `EPIC-035W`'s, not here.
"""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QLabel, QScrollArea
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_panel import (
    GridPanel,
)

from .bots_screen_fixtures import stored
from .connect_screen_helpers import poor_account, select


def _panel(screen) -> GridPanel:
    panel = screen.view._kind_panel
    assert isinstance(panel, GridPanel)
    return panel


def _poor_draft(open_bots_screen):
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    poor_account(screen, Decimal(800))
    screen.settle()
    select(screen, "a00001")
    screen.settle()
    return screen


def _marker(screen, key: str) -> QLabel:
    marker = _panel(screen).findChild(QLabel, f"lblGridMarker_{key}")
    assert marker is not None
    return marker


def test_a_field_with_a_verdict_carries_a_sign_beside_its_sentence(
    open_bots_screen,
) -> None:
    screen = _poor_draft(open_bots_screen)

    marker = _marker(screen, "capital_quote")

    assert not marker.isHidden()
    assert not marker.pixmap().isNull(), "a sign, not colour alone"
    assert marker.accessibleName() == "Blocks Start"
    assert marker.pixmap().devicePixelRatio() == marker.devicePixelRatioF()
    assert _marker(screen, "grid_count").isHidden()


def test_the_sign_goes_when_the_verdict_does(open_bots_screen) -> None:
    screen = _poor_draft(open_bots_screen)
    panel = _panel(screen)

    panel.capital.setText("500")
    panel.capital.textEdited.emit("500")
    screen.presenter._refresh_detail()

    assert _marker(screen, "capital_quote").isHidden()


def test_the_parameters_of_a_bot_at_rest_come_before_its_figures(
    open_bots_screen,
) -> None:
    screen = _poor_draft(open_bots_screen)
    plan = screen.view.plan

    assert plan.index_of_parameters() < plan.index_of_figures()


def test_the_reason_is_visible_without_scrolling_beside_its_field(
    open_bots_screen,
) -> None:
    screen = _poor_draft(open_bots_screen)
    screen.view.resize(1366, 768)
    screen.view.show()
    screen.settle()
    scroll = screen.view.plan.findChild(QScrollArea, "scrollBotPlan")
    label = _panel(screen).findChild(QLabel, "lblGridError_capital_quote")
    assert scroll is not None and label is not None

    top = label.mapTo(scroll.viewport(), QPoint(0, 0)).y()

    assert top >= 0
    assert top + label.height() <= scroll.viewport().height()


def test_a_bot_with_a_run_shows_its_figures_first(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.RUNNING)])
    screen.settle()
    select(screen, "a00001")
    screen.settle()
    plan = screen.view.plan

    assert plan.index_of_figures() < plan.index_of_parameters()


def test_the_chart_says_why_no_grid_is_drawn(open_bots_screen) -> None:
    screen = _poor_draft(open_bots_screen)
    panel = _panel(screen)

    panel.grid_count.lineEdit().setText("101")
    panel.grid_count.lineEdit().textEdited.emit("101")
    screen.presenter._refresh_detail()

    note = screen.view.chart_area.findChild(QLabel, "lblGridNotDrawn")
    assert note is not None and not note.isHidden()
    assert note.text().startswith("Grid not drawn: ")
    assert "101" in note.text()


def test_the_chart_says_nothing_while_the_grid_is_drawn(open_bots_screen) -> None:
    screen = _poor_draft(open_bots_screen)

    note = screen.view.chart_area.findChild(QLabel, "lblGridNotDrawn")

    assert note is None or note.isHidden()


def test_a_save_over_a_plan_start_refuses_says_so(open_bots_screen) -> None:
    screen = _poor_draft(open_bots_screen)
    panel = _panel(screen)
    panel.capital.setText("900")
    panel.capital.textEdited.emit("900")
    screen.presenter._refresh_detail()

    screen.view.model.action_requested.emit(BotAction.SAVE.value)
    screen.settle()

    text = screen.view.status.text()
    assert text.startswith("Save"), text
    assert "Start is still blocked" in text
    assert "has 800.00 USDT free" in text


def test_a_save_of_a_plan_that_can_start_says_only_that_it_is_done(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    select(screen, "a00001")
    screen.settle()

    screen.view.model.action_requested.emit(BotAction.SAVE.value)
    screen.settle()

    assert "blocked" not in screen.view.status.text()
