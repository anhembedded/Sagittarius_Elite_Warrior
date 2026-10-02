"""Every test's `deleteLater()` backlog is flushed before the next test runs.

@details pytest-qt's teardown closes each `qtbot.addWidget()` widget with
`close()` + `deleteLater()`, then calls `QApplication.processEvents()`. At
event-loop level 0 that call does **not** deliver `DeferredDelete`, so the
widget stays alive. Across one xdist worker's few thousand tests the backlog
grew to 171,874 live widgets (measured, 2026-09-29). The first test that
entered a real event loop (`qtbot.wait`/`waitUntil`/`waitSignal`) then
destroyed them all in one go: 21.6 s locally, longer under CI's coverage
tracing. That cost landed inside its own timeout, and
`test_preferred_height_scroll_area.py::test_content_that_grows_later_becomes_scrollable`
failed twice on PR #293 for it, depending on which worker xdist gave it to.

The root `tests/conftest.py` fixture `_release_finished_test_objects` fixes that
at the mechanism: it runs after pytest-qt has closed the widgets and
delivers their deferred deletes, so no test pays for another's cleanup.
"""

from __future__ import annotations

import pytest
import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.tests.conftest import flush_qt_deferred_deletes


def test_process_events_alone_leaves_a_deleted_later_widget_alive(qapp) -> None:
    """The trap itself: what pytest-qt's teardown relies on does not
    destroy anything at loop level 0. If Qt ever changed this, the fixture
    below would be redundant, and this test failing is how anyone would
    find out."""
    widget = QWidget()
    widget.deleteLater()

    QCoreApplication.processEvents()

    assert shiboken6.isValid(widget)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_the_flush_destroys_a_deleted_later_widget(qapp) -> None:
    widget = QWidget()
    widget.deleteLater()

    flush_qt_deferred_deletes()

    assert not shiboken6.isValid(widget)


def test_the_flush_is_wired_into_every_test(request: pytest.FixtureRequest) -> None:
    """The helper does nothing unless every test gets the fixture that
    calls it; remove `autouse=True` and this fails."""
    assert "_release_finished_test_objects" in request.fixturenames
