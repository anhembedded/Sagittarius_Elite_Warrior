"""`BUG-242` — a widget a slot gives up is never left as a window of its own.

@details `replace_in` took each widget out with `setParent(None)`: a parentless widget is a top-level
window, hidden only because Qt hides it on reparenting. A retired workbench page, chart or kind panel
was one such window, ready to appear at the screen's corner over the docks the moment anything shows
it. A widget that is kept leaves hidden and stays a child of the slot's owner; one that declared
itself disposable is deleted."""

from __future__ import annotations

import pytest
import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.widget_slot import (
    replace_in,
)


def _flush_deletions() -> None:
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _settle() -> None:
    """The layout shows an added widget from the event loop, not at once."""
    QCoreApplication.processEvents()


@pytest.fixture
def owner(qtbot):  # type: ignore[no-untyped-def]
    host = QWidget()
    qtbot.addWidget(host)
    slot = QVBoxLayout(host)
    host.slot = slot  # type: ignore[attr-defined]
    host.show()
    return host


def test_a_kept_widget_leaves_hidden_and_is_not_a_window(owner) -> None:  # type: ignore[no-untyped-def]
    first, second = QLabel("first"), QLabel("second")
    replace_in(owner.slot, first)
    _settle()
    assert first.isVisible()

    replace_in(owner.slot, second)
    _settle()

    assert not first.isVisible()
    assert not first.isWindow()
    assert first.parentWidget() is owner


def test_a_kept_widget_shows_again_when_it_comes_back(owner) -> None:  # type: ignore[no-untyped-def]
    first, second = QLabel("first"), QLabel("second")
    replace_in(owner.slot, first)
    replace_in(owner.slot, second)

    replace_in(owner.slot, first)
    _settle()

    assert first.isVisible() and not second.isVisible()


def test_a_disposable_widget_is_deleted_when_it_leaves(owner) -> None:  # type: ignore[no-untyped-def]
    note, page = QLabel("note"), QLabel("page")
    note.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    replace_in(owner.slot, note)

    replace_in(owner.slot, page)
    _flush_deletions()

    assert not shiboken6.isValid(note)
    assert owner.findChildren(QLabel) == [page]


def test_a_widget_put_back_in_the_slot_that_holds_it_stays(owner) -> None:  # type: ignore[no-untyped-def]
    """A disposable widget handed to the slot it is already in is not the one leaving."""
    editor = QLabel("editor")
    editor.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    replace_in(owner.slot, editor)

    replace_in(owner.slot, editor)
    _settle()
    _flush_deletions()

    assert shiboken6.isValid(editor)
    assert owner.slot.count() == 1 and editor.isVisible()


def test_a_slot_that_is_not_installed_in_a_widget_refuses_to_hold_one(qapp) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="installed in a widget"):
        replace_in(QVBoxLayout(), QLabel("orphan"))
