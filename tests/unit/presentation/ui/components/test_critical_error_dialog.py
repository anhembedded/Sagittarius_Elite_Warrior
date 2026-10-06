from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtWidgets import QDialogButtonBox, QPushButton
from Sagittarius_Elite_Warrior.src.presentation.ui.components.critical_error_dialog import (
    COPIED_TEXT,
    CriticalErrorDialog,
)


def _dialog() -> CriticalErrorDialog:
    return CriticalErrorDialog(
        title="Custom Error",
        message="Failure in subsystem",
        error_details="Index out of bounds",
        traceback_str="Traceback (most recent call last):\n  File 'foo.py', line 5",
    )


def test_critical_error_dialog_initialization(qapp) -> None:
    dialog = _dialog()

    assert dialog.windowTitle() == "Custom Error"
    assert dialog.isSizeGripEnabled() is True
    dialog.resize(800, 600)
    assert (dialog.width(), dialog.height()) == (800, 600)


def test_a_problem_closes_with_close_never_ok(qapp) -> None:
    """`ui-presentation-rule.md` §4, §7: the commit buttons are a button box,
    and a problem's one commit button is Close, the default."""
    dialog = _dialog()
    box = dialog.findChild(QDialogButtonBox)

    assert box is not None
    close = box.button(QDialogButtonBox.StandardButton.Close)
    assert close is not None and close.isDefault()
    texts = [b.text().replace("&", "") for b in dialog.findChildren(QPushButton)]
    assert "OK" not in texts


def test_the_details_toggle_is_a_check_box_and_shows_the_traceback(qapp) -> None:
    dialog = _dialog()

    assert dialog.details.isHidden() is True
    dialog.show_details.setChecked(True)
    assert dialog.details.isHidden() is False
    assert "foo.py" in dialog.details.toPlainText()
    dialog.show_details.setChecked(False)
    assert dialog.details.isHidden() is True


def test_the_traceback_is_in_the_platforms_fixed_pitch_font(qapp) -> None:
    fixed = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)

    assert _dialog().details.font().family() == fixed.family()


def test_critical_error_dialog_copy_to_clipboard(qapp) -> None:
    dialog = CriticalErrorDialog(
        title="Custom Error",
        message="Failure in subsystem",
        error_details="AttributeError: 'NoneType' object",
        traceback_str="Traceback:\n  File 'test.py', line 123",
    )

    dialog.copy_button.click()
    clipboard_text = QGuiApplication.clipboard().text()
    assert "AttributeError: 'NoneType' object" in clipboard_text
    assert "File 'test.py', line 123" in clipboard_text
    assert dialog.copy_button.text() == COPIED_TEXT
