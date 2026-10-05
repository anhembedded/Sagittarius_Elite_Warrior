"""`EPIC-033E` — Tools → Options holds each module's page, then Developer.

Replaces the Settings screen's sanity test: the pages come from the real
modules' contributions through the same `assemble_contributions()` and
`build_options_pages()` the composition root calls, and an edit typed into a
real field reaches `user_config.json` only when the dialog's Apply is clicked.
The file is the `app_engine` fixture's writable copy in `tmp_path`.
"""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialogButtonBox, QLabel, QLineEdit, QPushButton
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_reader import (
    IConfigReader,
)
from Sagittarius_Elite_Warrior.src.shell.contribution_assembly import (
    assemble_contributions,
)
from Sagittarius_Elite_Warrior.src.shell.options_pages import build_options_pages
from sagittarius_engine.extensions.pyside_mvc.workbench.options_dialog import (
    OptionsDialog,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

_APPLY = QDialogButtonBox.StandardButton.Apply


def _pages(app_engine):
    container = app_engine.context.container
    return build_options_pages(
        assemble_contributions(container, dev_mode=False),
        container,
        container.resolve(IConfigReader),
        running_with_dev_mode=False,
    )


def _apply_button(dialog: OptionsDialog) -> QPushButton:
    buttons = dialog.findChild(QDialogButtonBox)
    assert buttons is not None
    button = buttons.button(_APPLY)
    assert button is not None
    return button


def test_the_pages_are_each_modules_then_developer(qapp, app_engine) -> None:
    assert [page.title for page in _pages(app_engine)] == [
        "Trading",
        "Market Data",
        "Developer",
    ]


def test_an_edit_in_the_dialog_reaches_the_file_only_on_apply(
    qtbot, app_engine, tmp_path
) -> None:
    user_file = tmp_path / "user_config.json"
    dialog = OptionsDialog(_pages(app_engine))
    qtbot.addWidget(dialog)
    dialog.show()
    apply_button = _apply_button(dialog)
    assert not apply_button.isEnabled()

    field = dialog.findChild(QLineEdit, "txtDefaultSymbols")
    assert field is not None
    field.clear()
    qtbot.keyClicks(field, "ETHUSDT")

    assert apply_button.isEnabled()
    assert json.loads(user_file.read_text()).get("DEFAULT_SYMBOLS") != ["ETHUSDT"]

    qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)

    assert json.loads(user_file.read_text())["DEFAULT_SYMBOLS"] == ["ETHUSDT"]
    assert not apply_button.isEnabled()


def test_cancel_leaves_the_file_and_puts_the_saved_value_back(
    qtbot, app_engine, tmp_path
) -> None:
    user_file = tmp_path / "user_config.json"
    before = user_file.read_text()
    dialog = OptionsDialog(_pages(app_engine))
    qtbot.addWidget(dialog)
    dialog.show()
    field = dialog.findChild(QLineEdit, "txtDefaultSymbols")
    assert field is not None
    saved_text = field.text()
    field.clear()
    qtbot.keyClicks(field, "ETHUSDT")

    dialog.reject()

    assert user_file.read_text() == before
    assert field.text() == saved_text


def test_an_invalid_page_keeps_ok_disabled_and_says_why(qtbot, app_engine) -> None:
    dialog = OptionsDialog(_pages(app_engine))
    qtbot.addWidget(dialog)
    dialog.show()
    field = dialog.findChild(QLineEdit, "txtDefaultSymbols")
    assert field is not None
    field.selectAll()
    qtbot.keyClick(field, Qt.Key.Key_Delete)

    buttons = dialog.findChild(QDialogButtonBox)
    assert buttons is not None
    ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert ok_button is not None
    assert not ok_button.isEnabled()
    message = dialog.findChild(QLabel, "workbench::options::message")
    assert message is not None
    assert message.text() == "Market Data: Default Symbols must not be empty."


def test_a_write_that_fails_changes_nothing_and_keeps_the_edit(
    qtbot, app_engine, tmp_path, monkeypatch
) -> None:
    """PR #348 review: when `user_config.json` cannot be written, the live
    config must not keep the value either, or the session runs on it and a
    later Cancel takes it as saved. The edit stays on the page, dirty."""

    def refuse(_self) -> None:
        raise OSError("read-only file system")

    monkeypatch.setattr(ConfigManager, "save", refuse)
    user_file = tmp_path / "user_config.json"
    before = user_file.read_text()
    config = app_engine.context.container.resolve(IConfigReader)
    saved_symbols = config.get("DEFAULT_SYMBOLS")
    dialog = OptionsDialog(_pages(app_engine))
    qtbot.addWidget(dialog)
    dialog.show()
    field = dialog.findChild(QLineEdit, "txtDefaultSymbols")
    assert field is not None
    saved_text = field.text()
    field.clear()
    qtbot.keyClicks(field, "ETHUSDT")

    qtbot.mouseClick(_apply_button(dialog), Qt.MouseButton.LeftButton)

    assert user_file.read_text() == before
    assert config.get("DEFAULT_SYMBOLS") == saved_symbols
    assert field.text() == "ETHUSDT"
    assert _apply_button(dialog).isEnabled()
    status = dialog.findChild(QLabel, "lblMarketDataSettingsStatus")
    assert status is not None
    assert "nothing was changed" in status.text()

    dialog.reject()

    assert field.text() == saved_text
    assert config.get("DEFAULT_SYMBOLS") == saved_symbols


def test_ok_after_a_write_that_fails_keeps_the_dialog_open(
    qtbot, app_engine, monkeypatch
) -> None:
    """Engine `BUG-018`, pinned by `engine.ref`: OK closed the dialog even
    when a page could not save, so the page's error was shown in a dialog
    that had already closed."""

    def refuse(_self) -> None:
        raise OSError("read-only file system")

    monkeypatch.setattr(ConfigManager, "save", refuse)
    dialog = OptionsDialog(_pages(app_engine))
    qtbot.addWidget(dialog)
    dialog.show()
    field = dialog.findChild(QLineEdit, "txtDefaultSymbols")
    assert field is not None
    field.clear()
    qtbot.keyClicks(field, "ETHUSDT")
    buttons = dialog.findChild(QDialogButtonBox)
    assert buttons is not None
    ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert ok_button is not None

    qtbot.mouseClick(ok_button, Qt.MouseButton.LeftButton)

    assert dialog.isVisible()
    message = dialog.findChild(QLabel, "workbench::options::message")
    assert message is not None
    assert message.text() == "Market Data: the changes could not be applied."
