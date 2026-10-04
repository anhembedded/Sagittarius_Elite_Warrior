"""`EPIC-033C` — Tools → Options → Developer: the developer-mode switch that
lived on Welcome, now under the Options dialog's OK, Cancel and Apply.

Against the real `ConfigManager` and `ConfigManagerWriter` over a writable
file in `tmp_path`: what the page promises is a fact about that file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtWidgets import QCheckBox, QPushButton
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_writer import IConfigWriter
from Sagittarius_Elite_Warrior.src.shell.config_writer import ConfigManagerWriter
from Sagittarius_Elite_Warrior.src.shell.developer_options.developer_options_page import (
    DeveloperOptionsPage,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

_KEY = "dev.mode"


def _config(tmp_path: Path, *, dev_mode: bool) -> tuple[ConfigManager, Path]:
    user_file = tmp_path / "user_config.json"
    user_file.write_text(json.dumps({_KEY: dev_mode}))
    config = ConfigManager()
    config.load_json(str(user_file), writable=True)
    return config, user_file


def _page(
    config: ConfigManager, *, running: bool, writer: IConfigWriter | None = None
) -> DeveloperOptionsPage:
    return DeveloperOptionsPage(
        config,
        writer or ConfigManagerWriter(config),
        running_with_dev_mode=running,
    )


def _switch(page: DeveloperOptionsPage) -> QCheckBox:
    switch = page.widget().findChild(QCheckBox, "options::developer::mode")
    assert switch is not None
    return switch


def _restart(page: DeveloperOptionsPage) -> QPushButton:
    button = page.widget().findChild(QPushButton, "options::developer::restart")
    assert button is not None
    return button


def test_the_page_opens_on_the_saved_value_with_no_restart_offered(
    qapp, tmp_path
) -> None:
    config, _ = _config(tmp_path, dev_mode=True)
    page = _page(config, running=True)

    assert page.title == "Developer"
    assert _switch(page).isChecked() is True
    assert page.is_dirty() is False
    assert _restart(page).isHidden()


def test_ticking_the_switch_is_an_edit_the_dialog_hears_and_nothing_is_written(
    qapp, tmp_path
) -> None:
    config, user_file = _config(tmp_path, dev_mode=False)
    page = _page(config, running=False)
    heard: list[str] = []
    page.set_change_listener(lambda: heard.append("edited"))

    _switch(page).setChecked(True)

    assert heard == ["edited"]
    assert page.is_dirty() is True
    assert json.loads(user_file.read_text())[_KEY] is False


def test_apply_writes_the_file_and_then_offers_the_restart(qapp, tmp_path) -> None:
    config, user_file = _config(tmp_path, dev_mode=False)
    page = _page(config, running=False)
    _switch(page).setChecked(True)

    page.apply()

    assert json.loads(user_file.read_text())[_KEY] is True
    assert page.is_dirty() is False
    assert not _restart(page).isHidden()


def test_cancel_puts_the_switch_back_to_the_saved_value(qapp, tmp_path) -> None:
    config, _ = _config(tmp_path, dev_mode=False)
    page = _page(config, running=False)
    _switch(page).setChecked(True)

    page.revert()

    assert _switch(page).isChecked() is False
    assert page.is_dirty() is False


class _RefusingWriter(IConfigWriter):
    """A read-only file: the value is recorded, the save fails."""

    def __init__(self, config: ConfigManager) -> None:
        self._inner = ConfigManagerWriter(config)

    def set(self, key: str, value: object) -> None:
        self._inner.set(key, value)

    def save(self) -> None:
        raise OSError("read-only file")


def test_a_failed_save_offers_no_restart_and_shows_what_is_on_disk(
    qapp, tmp_path, caplog: pytest.LogCaptureFixture
) -> None:
    config, user_file = _config(tmp_path, dev_mode=False)
    page = _page(config, running=False, writer=_RefusingWriter(config))
    _switch(page).setChecked(True)

    page.apply()

    assert json.loads(user_file.read_text())[_KEY] is False
    assert _restart(page).isHidden()
    assert "was not saved" in caplog.text
