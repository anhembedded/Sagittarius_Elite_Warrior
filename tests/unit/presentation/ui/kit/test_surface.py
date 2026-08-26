"""Tests for `widgets.surface` — `Surface`/`Panel`/`Card`."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QFrame, QLabel
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    Card,
    Panel,
    SelectableCard,
    Surface,
)


def test_surface_itself_is_abstract(qtbot):
    with pytest.raises(TypeError, match="Surface is abstract"):
        Surface()


def test_panel_constructs_as_a_qframe(qtbot):
    panel = Panel()
    qtbot.addWidget(panel)

    assert isinstance(panel, QFrame)
    assert panel.styleSheet() != ""


def test_panel_body_layout_accepts_content(qtbot):
    panel = Panel()
    qtbot.addWidget(panel)

    label = QLabel("hello")
    panel.body_layout.addWidget(label)

    assert panel.body_layout.count() == 1


def test_card_exposes_title_and_it_is_mutable(qtbot):
    card = Card("Sync Controls")
    qtbot.addWidget(card)

    assert card.title == "Sync Controls"

    card.title = "Renamed"
    assert card.title == "Renamed"


def test_card_header_actions_is_a_separate_layout_from_body(qtbot):
    card = Card("Log")
    qtbot.addWidget(card)

    from PySide6.QtWidgets import QPushButton

    button = QPushButton("Clear")
    card.header_actions.addWidget(button)

    # header content must not land in body_layout, which is where a
    # subclass/consumer's own content goes.
    assert card.body_layout.count() == 1  # just the header widget itself
    assert card.header_actions.count() == 1


def test_card_is_concrete_not_abstract(qtbot):
    # Unlike Surface, Card is directly usable — no type(self) is Card guard.
    card = Card("Standalone")
    qtbot.addWidget(card)
    assert card.title == "Standalone"


def test_setenabled_cascades_to_body_layout_children(qtbot):
    from PySide6.QtWidgets import QPushButton

    card = Card("X")
    qtbot.addWidget(card)
    button = QPushButton("Action")
    card.body_layout.addWidget(button)

    card.setEnabled(False)

    assert button.isEnabled() is False


def test_card_qss_is_scoped_to_its_exact_class(qtbot):
    """BUG-008 regression, in its corrected form.

    `SURFACE`'s QSS was first a bare property list — Qt's universal
    selector — so setting it on a `Card` repainted every unstyled
    descendant. Scoping it to the widget's runtime class fixed that and was
    still not enough: **a Qt type selector matches subclasses**, and
    `QLabel` is a `QFrame` subclass, so `QFrame { border: ... }` on a plain
    container still boxed every label inside it.

    The exact-class form is what the assertion pins. A leading dot is one
    character and the whole difference.
    """
    card = Card("X")
    qtbot.addWidget(card)

    assert card.styleSheet().startswith(".Card {")


def test_a_label_inside_a_frame_scoped_card_keeps_its_own_look(qtbot):
    """The symptom a user reported: three labels in a stat tile each drew
    their own box, and their stylesheets declared only colour and size.

    `QFrame` is the case that matters, because `QLabel` inherits it — a
    `QLineEdit` or `QPushButton` child never showed the bug, which is
    exactly the subclass relation and how the cause was pinned down.
    """
    from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout
    from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
        StyleRole,
        apply_role,
    )

    tile = QFrame()
    qtbot.addWidget(tile)
    apply_role(tile, StyleRole.SURFACE)
    layout = QVBoxLayout(tile)
    layout.addWidget(QLabel("Stored KLines Records"))

    assert tile.styleSheet().startswith(".QFrame {")
    assert not tile.styleSheet().startswith("QFrame {")


def test_unstyled_child_of_a_card_is_not_touched(qtbot):
    """BUG-008 requirement 5. A `Card` scoping its own QSS to itself must
    leave a child with no stylesheet of its own exactly as it was — this
    is the toolbar-buttons symptom that surfaced the bug."""
    from PySide6.QtWidgets import QPushButton

    card = Card("X")
    qtbot.addWidget(card)
    button = QPushButton("Action")
    card.body_layout.addWidget(button)

    assert button.styleSheet() == ""


def test_on_enabled_changed_hook_fires_on_setenabled(qtbot):
    calls: list[bool] = []

    class TrackingPanel(Panel):
        def _on_enabled_changed(self, enabled: bool) -> None:
            calls.append(enabled)

    panel = TrackingPanel()
    qtbot.addWidget(panel)

    panel.setEnabled(False)
    panel.setEnabled(True)

    assert calls == [False, True]


def test_selectable_card_is_a_bare_panel(qtbot):
    card = SelectableCard()
    qtbot.addWidget(card)

    assert isinstance(card, Panel)
    assert isinstance(card, QFrame)
    assert card.styleSheet() != ""


def test_selectable_card_starts_unselected(qtbot):
    card = SelectableCard()
    qtbot.addWidget(card)

    assert card.selected is False


def test_selectable_card_selected_setter_changes_its_stylesheet(qtbot):
    card = SelectableCard()
    qtbot.addWidget(card)
    unselected_qss = card.styleSheet()

    card.selected = True

    assert card.selected is True
    assert card.styleSheet() != unselected_qss


def test_selectable_card_click_emits_clicked_only_when_press_and_release_are_both_inside(
    qtbot,
):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    card = SelectableCard()
    qtbot.addWidget(card)
    card.resize(100, 40)

    clicks: list[None] = []
    card.clicked.connect(lambda: clicks.append(None))

    inside = QPointF(50, 20)
    outside = QPointF(500, 500)

    def _press(pos: QPointF) -> QMouseEvent:
        return QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            pos,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

    def _release(pos: QPointF) -> QMouseEvent:
        return QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            pos,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )

    card.mousePressEvent(_press(inside))
    card.mouseReleaseEvent(_release(inside))
    assert clicks == [None]

    card.mousePressEvent(_press(inside))
    card.mouseReleaseEvent(_release(outside))
    assert clicks == [None]  # unchanged — release landed outside
