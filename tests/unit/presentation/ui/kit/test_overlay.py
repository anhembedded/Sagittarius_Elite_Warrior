"""Tests for `widgets.overlay.Overlay`."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    Overlay,
    StyleRole,
    apply_role,
)


class _ConfirmOverlay(Overlay):
    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        self.confirm_button = QPushButton("Confirm")
        row.addWidget(self.cancel_button)
        row.addWidget(self.confirm_button)
        return row


def test_overlay_itself_is_abstract(qtbot):
    with pytest.raises(TypeError, match="Overlay is abstract"):
        Overlay("title")


def test_abstract_error_only_names_subclasses_that_exist(qtbot):
    """BUG-004: the message told the reader to instantiate `ConfirmOverlay`
    or `PickerOverlay`, and neither existed anywhere in the shipped package
    — an error message sending someone to an API nobody wrote.

    Asserted by resolving the names out of the message itself rather than
    against a hardcoded list, so rewording the suggestion cannot quietly
    reintroduce a phantom: whatever it names, it must be importable."""
    import re

    from Sagittarius_Elite_Warrior.src.presentation.ui import kit as widgets

    with pytest.raises(TypeError) as excinfo:
        Overlay("title")

    suggested = re.findall(r"\b([A-Z]\w*Overlay)\b", str(excinfo.value))
    suggested = [name for name in suggested if name != "Overlay"]

    assert suggested, "the message should still suggest at least one subclass"
    for name in suggested:
        resolved = getattr(widgets, name, None)
        assert resolved is not None, f"{name} is named but does not resolve"
        assert issubclass(resolved, Overlay)
        assert name in widgets.__all__


def test_subclass_constructs_as_a_qdialog(qtbot):
    overlay = _ConfirmOverlay("Confirm delete")
    qtbot.addWidget(overlay)

    assert isinstance(overlay, QDialog)
    assert overlay.isModal() is True
    assert overlay.styleSheet() != ""


def test_the_surface_background_is_actually_paintable(qtbot):
    """`BUG-102`: `Overlay` is a bare `QDialog` (not a `QFrame`, unlike
    `Surface`/`Panel`/`Card`), so its `StyleRole.SURFACE` stylesheet never
    painted without this attribute — Qt's own style sheet reference: a
    plain `QWidget` subclass "needs to set the Qt::WA_StyledBackground
    attribute for the style sheet to have an effect". A `QmlOverlay`
    subclass's QML body relies on exactly this background showing through
    its own transparent clear colour (`host.py`); without it the whole
    dialog rendered see-through to whatever sat behind it."""
    overlay = _ConfirmOverlay("Confirm delete")
    qtbot.addWidget(overlay)

    assert overlay.testAttribute(Qt.WidgetAttribute.WA_StyledBackground) is True


def test_title_and_subtitle_properties(qtbot):
    overlay = _ConfirmOverlay("Title", "Subtitle text")
    qtbot.addWidget(overlay)

    assert overlay.title == "Title"
    assert overlay.subtitle == "Subtitle text"


def test_subtitle_defaults_to_hidden_when_empty(qtbot):
    overlay = _ConfirmOverlay("Title only")
    qtbot.addWidget(overlay)

    assert overlay._subtitle_label.isVisibleTo(overlay) is False


def test_subtitle_becomes_visible_when_set(qtbot):
    overlay = _ConfirmOverlay("Title")
    qtbot.addWidget(overlay)

    overlay.subtitle = "Now visible"

    # isVisible() would stay False here regardless — it also requires the
    # top-level dialog itself to have been shown, which this fast unit
    # test deliberately never does. isVisibleTo(overlay) reflects the
    # requested visibility relative to its own parent instead (verified
    # empirically: a freshly setVisible(True) child of an unshown QDialog
    # reports isVisible()=False but isVisibleTo(parent)=True).
    assert overlay._subtitle_label.isVisibleTo(overlay) is True


def test_build_buttons_result_is_wired_into_the_dialog(qtbot):
    overlay = _ConfirmOverlay("Confirm")
    qtbot.addWidget(overlay)

    assert overlay.cancel_button.text() == "Cancel"
    assert overlay.confirm_button.text() == "Confirm"


def test_body_layout_accepts_content(qtbot):
    from PySide6.QtWidgets import QLabel

    overlay = _ConfirmOverlay("Confirm")
    qtbot.addWidget(overlay)

    overlay.body_layout.addWidget(QLabel("Are you sure?"))

    assert overlay.body_layout.count() == 1


def test_default_build_buttons_is_an_empty_row(qtbot):
    class _NoButtonsOverlay(Overlay):
        pass

    overlay = _NoButtonsOverlay("No buttons")
    qtbot.addWidget(overlay)
    # Constructs without error, matching the "not @abstractmethod" call in
    # Overlay._build_buttons()'s own docstring.


def test_the_header_labels_carry_roles(qtbot, fake_theme_bridge):
    """Both shipped unstyled, so a dialog header rendered at the widget
    default while the body around it was token-styled."""
    overlay = _ConfirmOverlay("Title", "Subtitle")
    qtbot.addWidget(overlay)

    assert overlay._title_label.styleSheet() != ""
    assert overlay._subtitle_label.styleSheet() != ""
    assert overlay._title_label.styleSheet() != overlay._subtitle_label.styleSheet()


def test_the_title_label_is_reachable_for_a_louder_treatment(qtbot, fake_theme_bridge):
    """An app can carry more than one dialog treatment — a destructive
    confirm reads louder than a parameter modal. Re-roling one label is the
    difference; rebuilding the header to change it is not."""
    overlay = _ConfirmOverlay("Title")
    qtbot.addWidget(overlay)
    before = overlay.title_label.styleSheet()

    apply_role(overlay.title_label, StyleRole.HEADING)

    assert overlay.title_label is overlay._title_label
    assert overlay.title_label.styleSheet() != before
