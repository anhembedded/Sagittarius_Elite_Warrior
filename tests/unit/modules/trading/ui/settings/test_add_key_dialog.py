"""`BUG-176` — the Add Key dialog masks both fields and clears them on close."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QDialogButtonBox, QLineEdit
from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.add_key_dialog import (
    AddKeyDialog,
)


def _dialog(qapp, request) -> AddKeyDialog:
    dialog = AddKeyDialog("Enter the key.")
    request.addfinalizer(dialog.deleteLater)
    return dialog


def _ok(dialog: AddKeyDialog):
    return dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)


def test_both_fields_are_masked(qapp, request) -> None:
    dialog = _dialog(qapp, request)

    modes = {f.echoMode() for f in dialog.findChildren(QLineEdit)}

    assert modes == {QLineEdit.EchoMode.Password}
    assert len(dialog.findChildren(QLineEdit)) == 2


def test_ok_waits_for_both_the_key_and_the_secret(qapp, request) -> None:
    dialog = _dialog(qapp, request)
    key = dialog.findChild(QLineEdit, "txtNewApiKey")
    secret = dialog.findChild(QLineEdit, "txtNewApiSecret")
    assert not _ok(dialog).isEnabled()

    key.setText("k")
    assert not _ok(dialog).isEnabled()
    secret.setText("   ")
    assert not _ok(dialog).isEnabled()
    secret.setText("s")
    assert _ok(dialog).isEnabled()


def test_what_is_entered_comes_back_trimmed_and_the_fields_are_cleared_on_close(
    qapp, request
) -> None:
    dialog = _dialog(qapp, request)
    dialog.findChild(QLineEdit, "txtNewApiKey").setText("  the-key \n")
    dialog.findChild(QLineEdit, "txtNewApiSecret").setText("the-secret ")
    entered = dialog.entered()

    dialog.accept()

    assert entered == ("the-key", "the-secret")
    assert [f.text() for f in dialog.findChildren(QLineEdit)] == ["", ""]


def test_the_dialog_is_titled_for_the_command_that_opened_it(qapp, request) -> None:
    assert _dialog(qapp, request).windowTitle() == "Add Key"
