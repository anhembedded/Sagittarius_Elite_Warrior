"""`EPIC-029F` (ADR O4) — the question the window asks before it closes on
something still running.

@details Injectable, in the shape `AccountTabConfirmations` established, so a
test closes the window without a modal dialog waiting for a click. Cancel is
the default button: the safe answer to a question about live orders is the
one an accidental Enter gives.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtWidgets import QMessageBox, QWidget

#: Answers whether to close despite `reasons`; True closes.
type ConfirmClose = Callable[[Sequence[str]], bool]

CLOSE_ANYWAY_TEXT = "Close anyway"


def close_question(reasons: Sequence[str]) -> str:
    return "\n\n".join([*reasons, "Close the app anyway?"])


def ask_before_closing(parent: QWidget, reasons: Sequence[str]) -> bool:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("Close Sagittarius?")
    box.setText(close_question(reasons))
    close_anyway = box.addButton(
        CLOSE_ANYWAY_TEXT, QMessageBox.ButtonRole.DestructiveRole
    )
    cancel = box.addButton(QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(cancel)
    box.exec()
    return box.clickedButton() is close_anyway
