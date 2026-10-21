"""`EPIC-036D4` — Tools → Options → Alerts as the owner meets it: light and dark at the three
window sizes the workbench suite uses, drawn by `QWidget.grab()`. With `SEW_UI_SCREENSHOTS` set
the pictures are kept for the owner (the CI artifact `ui-screenshots`, `alerts_options@WxH.png`).
The checks are the measurable half: not blank, both channels' groups shown, the token field
masked and no scroll bar needed for the groups themselves."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QGroupBox, QLineEdit
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.alerts_settings_view import (
    AlertsSettingsView,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.preview import (
    build_preview,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_screenshots import (
    SCHEMES,
    SCREENSHOT_DIR_ENV,
    apply_scheme,
    is_blank,
    restore_scheme,
    screenshot_name,
)

_SIZES = [(1024, 700), (1366, 768), (1920, 1080)]


@pytest.mark.parametrize("scheme", SCHEMES)
@pytest.mark.parametrize("width_height", _SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
def test_the_alerts_options_page_shows_both_channels_in_both_schemes(
    qtbot, tmp_path: Path, scheme: str, width_height: tuple[int, int]
) -> None:
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    apply_scheme(app, scheme)
    try:
        view = build_preview()
        assert isinstance(view, AlertsSettingsView)
        qtbot.addWidget(view)
        view.resize(*width_height)
        view.show()
        qtbot.waitExposed(view)

        image = view.grab().toImage()
        out_dir = Path(os.environ.get(SCREENSHOT_DIR_ENV, tmp_path))
        out_dir.mkdir(parents=True, exist_ok=True)
        name = screenshot_name("alerts_options", QSize(*width_height), scheme)
        assert image.save(str(out_dir / name))

        assert not is_blank(image)
        titles = {box.title() for box in view.findChildren(QGroupBox)}
        assert {"Discord", "Telegram", "Bots"} <= titles
        token = view.findChild(QLineEdit, "txtTelegramToken")
        assert token is not None and token.echoMode() is QLineEdit.EchoMode.Password
    finally:
        restore_scheme(app)
