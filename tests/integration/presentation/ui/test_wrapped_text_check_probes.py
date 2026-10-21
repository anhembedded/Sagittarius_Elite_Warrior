"""Probes for the conformance suite's wrapped-text check (`BUG-248`): it sees a wrapped label
shorter than its text, does not see one parked behind a tab, sees it once its tab is raised, and
still sees one squeezed to no height at all.

Retire when: the checks they probe are retired with the conformance suite.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QLabel,
    QMainWindow,
    QSplitter,
    QWidget,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_layout_checks import (
    wrapped_text_in_every_tab,
    wrapped_text_problems,
)

_TEXT = "A sentence long enough to wrap over several lines in a narrow panel " * 3


def _settle() -> None:
    for _ in range(3):
        QApplication.processEvents()


def _window_with_two_tabs(qtbot) -> tuple[QMainWindow, QLabel]:
    window = QMainWindow()
    qtbot.addWidget(window)
    window.setCentralWidget(QWidget())
    front = QDockWidget("Front", window)
    front.setWidget(QLabel("front"))
    back = QDockWidget("Back", window)
    clipped = QLabel(_TEXT)
    clipped.setObjectName("lblClipped")
    clipped.setWordWrap(True)
    back.setWidget(clipped)
    window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, front)
    window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, back)
    window.tabifyDockWidget(front, back)
    window.resize(300, 300)
    window.show()
    front.raise_()
    _settle()
    return window, clipped


def test_a_label_parked_behind_a_tab_is_read_only_with_its_tab_in_front(qtbot) -> None:
    window, clipped = _window_with_two_tabs(qtbot)
    # Cut it short, as a layout that gave it too little would.
    clipped.setFixedHeight(clipped.fontMetrics().height())

    assert clipped.visibleRegion().isEmpty()
    assert wrapped_text_problems(window, window) == []

    found = wrapped_text_in_every_tab(window, window)

    assert len(found) == 1 and "lblClipped" in found[0] and "tab 'Back'" in found[0]


def test_a_wrapped_label_with_no_height_at_all_is_still_seen(qtbot) -> None:
    page = QSplitter(Qt.Orientation.Vertical)
    qtbot.addWidget(page)
    label = QLabel(_TEXT)
    label.setObjectName("lblSqueezed")
    label.setWordWrap(True)
    page.addWidget(label)
    page.addWidget(QWidget())
    page.resize(200, 400)
    page.show()
    page.setSizes([0, 400])
    _settle()

    assert label.height() == 0
    assert any("lblSqueezed" in p for p in wrapped_text_problems(QMainWindow(), page))
