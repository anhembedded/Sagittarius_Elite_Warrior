from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication
from Sagittarius_Elite_Warrior.src.presentation.ui.components.critical_error_dialog import (
    CriticalErrorDialog,
)


def test_critical_error_dialog_initialization(qapp) -> None:
    dialog = CriticalErrorDialog(
        title="Custom Error",
        message="Failure in subsystem",
        error_details="Index out of bounds",
        traceback_str="Traceback (most recent call last):\n  File 'foo.py', line 5",
    )

    assert dialog.windowTitle() == "Custom Error"
    assert dialog.isSizeGripEnabled() is True
    assert dialog.minimumWidth() >= 500
    assert dialog.minimumHeight() >= 200

    # Resizing works properly
    dialog.resize(800, 600)
    assert dialog.width() == 800
    assert dialog.height() == 600


def test_critical_error_dialog_toggle_details(qapp) -> None:
    dialog = CriticalErrorDialog(
        title="Custom Error",
        message="Failure in subsystem",
        error_details="Index out of bounds",
        traceback_str="Traceback lines...",
    )

    assert dialog._details_edit.isHidden() is True
    assert dialog._btn_details.text() == "Show Details..."

    dialog._btn_details.setChecked(True)
    dialog._toggle_details()
    assert dialog._details_edit.isHidden() is False
    assert dialog._btn_details.text() == "Hide Details..."

    dialog._btn_details.setChecked(False)
    dialog._toggle_details()
    assert dialog._details_edit.isHidden() is True
    assert dialog._btn_details.text() == "Show Details..."


def test_critical_error_dialog_copy_to_clipboard(qapp) -> None:
    dialog = CriticalErrorDialog(
        title="Custom Error",
        message="Failure in subsystem",
        error_details="AttributeError: 'NoneType' object",
        traceback_str="Traceback:\n  File 'test.py', line 123",
    )

    dialog._copy_to_clipboard()
    clipboard_text = QGuiApplication.clipboard().text()
    assert "AttributeError: 'NoneType' object" in clipboard_text
    assert "File 'test.py', line 123" in clipboard_text
    assert dialog._btn_copy.text() == "Copied!"
