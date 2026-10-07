"""`BUG-176` — the Add Key dialog masks both fields and clears them on close."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QLineEdit
from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.add_key_dialog import (
    AddKeyDialog,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.trading_settings_view import (
    TradingSettingsView,
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


def test_what_is_entered_comes_back_trimmed_and_taking_it_clears_the_fields(
    qapp, request
) -> None:
    dialog = _dialog(qapp, request)
    dialog.findChild(QLineEdit, "txtNewApiKey").setText("  the-key \n")
    dialog.findChild(QLineEdit, "txtNewApiSecret").setText("the-secret ")

    dialog.accept()
    assert dialog.entered() == ("the-key", "the-secret")  # still there after OK
    entry = dialog.take_entry()

    assert entry == ("the-key", "the-secret")
    assert [f.text() for f in dialog.findChildren(QLineEdit)] == ["", ""]


def test_the_dialog_is_titled_for_the_command_that_opened_it(qapp, request) -> None:
    assert _dialog(qapp, request).windowTitle() == "Add Key"


def test_the_view_hands_back_what_was_typed_when_the_dialog_is_accepted(
    qapp, request
) -> None:
    """The reviewer's blocker on PR #423: the dialog cleared its fields as it closed,
    before the view read them, so every Add key came back empty. This runs the real
    dialog through the view's own `ask_for_key`."""
    view = TradingSettingsView()
    request.addfinalizer(view.deleteLater)

    def type_and_accept() -> None:
        dialog = next(
            w for w in QApplication.topLevelWidgets() if isinstance(w, AddKeyDialog)
        )
        dialog.findChild(QLineEdit, "txtNewApiKey").setText("the-key")
        dialog.findChild(QLineEdit, "txtNewApiSecret").setText("the-secret")
        dialog.accept()

    QTimer.singleShot(0, type_and_accept)

    assert view.ask_for_key("hint") == ("the-key", "the-secret")


def test_cancelling_the_real_dialog_hands_back_nothing(qapp, request) -> None:
    view = TradingSettingsView()
    request.addfinalizer(view.deleteLater)
    QTimer.singleShot(
        0,
        lambda: next(
            w for w in QApplication.topLevelWidgets() if isinstance(w, AddKeyDialog)
        ).reject(),
    )

    assert view.ask_for_key("hint") is None
