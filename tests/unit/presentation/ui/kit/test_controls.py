"""Tests for `widgets.controls` — `StyledButton`/`StyledCheckBox`/
`StyledField`/`DateTimeField`, each a single-inheritance subclass of its
own distinct Qt base (see module docstring for why `DateTimeField` extends
`QDateTimeEdit` directly rather than `StyledField`)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QCheckBox, QDateTimeEdit, QLineEdit, QPushButton
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    DateTimeField,
    StyledButton,
    StyledCheckBox,
    StyledField,
    StyleRole,
)


def test_styled_button_is_a_real_qpushbutton(qtbot):
    button = StyledButton("Save", role=StyleRole.PRIMARY_BUTTON)
    qtbot.addWidget(button)

    assert isinstance(button, QPushButton)
    assert button.text() == "Save"
    assert button.styleSheet() != ""


def test_styled_button_rejects_a_non_button_role(qtbot):
    with pytest.raises(ValueError, match="StyledButton role must be one of"):
        StyledButton("x", role=StyleRole.SURFACE)


@pytest.mark.parametrize(
    "role",
    [StyleRole.PRIMARY_BUTTON, StyleRole.SECONDARY_BUTTON, StyleRole.DANGER_BUTTON],
)
def test_styled_button_accepts_every_button_role(qtbot, role):
    button = StyledButton("x", role=role)
    qtbot.addWidget(button)
    assert button.styleSheet() != ""


def test_styled_button_restyles_on_setenabled(qtbot, fake_theme_bridge):
    button = StyledButton("x", role=StyleRole.DANGER_BUTTON)
    qtbot.addWidget(button)
    enabled_qss = button.styleSheet()

    button.setEnabled(False)

    assert button.styleSheet() != enabled_qss
    assert button.isEnabled() is False


def test_styled_checkbox_is_a_real_qcheckbox(qtbot):
    checkbox = StyledCheckBox("Enable X")
    qtbot.addWidget(checkbox)

    assert isinstance(checkbox, QCheckBox)
    assert checkbox.text() == "Enable X"
    assert checkbox.styleSheet() != ""


def test_styled_field_is_a_real_qlineedit(qtbot):
    field = StyledField()
    qtbot.addWidget(field)

    assert isinstance(field, QLineEdit)
    assert field.styleSheet() != ""


def test_datetime_field_is_a_real_qdatetimeedit_not_a_lineedit_subclass(qtbot):
    field = DateTimeField()
    qtbot.addWidget(field)

    assert isinstance(field, QDateTimeEdit)
    assert not isinstance(field, QLineEdit)
    assert field.styleSheet() != ""
