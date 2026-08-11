"""
@brief Application entry-point bootstrapper.

@details
Responsible for:
- Booting the Sagittarius Engine (config + create_app).
- Initialising QApplication (font, theme, exception handler).
- Creating and showing MainWindow.
- Shutting down the Engine on exit.

This module owns the `main()` function so that `MainWindow` is a pure
assembly component with no Engine-boot side effects.
"""

from __future__ import annotations

import os
import sys
import traceback

import qdarktheme
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.main import create_app
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
    get_icon_loader,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
from sagittarius_engine.extensions.pyside_mvc import configure_app_qml
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.interfaces.i_config import IConfig

# ---------------------------------------------------------------------------
# Config file paths — resolved relative to this file's location
# ---------------------------------------------------------------------------
_CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config"
)
_APP_CONFIG = os.path.join(_CONFIG_DIR, "app_config.json")
_USER_CONFIG = os.path.join(_CONFIG_DIR, "user_config.json")


def main() -> None:
    """Application entry point — boot Engine, boot UI, run event loop, shutdown."""
    # ------------------------------------------------------------------ #
    # 1. Boot the Sagittarius Engine
    # ------------------------------------------------------------------ #
    config_manager = ConfigManager()
    config_manager.load_json(_APP_CONFIG)
    config_manager.load_json(_USER_CONFIG, writable=True)

    if "--dev" in sys.argv:
        config_manager.load_dict({ConfigKeys.DEV_MODE.value: True})
        print(
            "Dev mode enabled — button clicks are auto-logged for real "
            "QPushButtons only (e.g. ChartCard's timeframe toolbar); QML "
            "screens are not instrumented (see BaseView._ButtonClickWatcher)."
        )

    app_engine = create_app(config_manager)
    app_engine.boot()

    # ------------------------------------------------------------------ #
    # 2. Boot PySide6 QApplication
    # ------------------------------------------------------------------ #
    app = QApplication(sys.argv)

    _install_exception_handler(app_engine)
    _apply_font(app, config_manager)
    _apply_theme(app, config_manager)
    configure_app_qml(Palette.as_ui_dict(), get_icon_loader(), Palette.as_icon_dict())

    # ------------------------------------------------------------------ #
    # 3. Create and show MainWindow
    # ------------------------------------------------------------------ #
    window = MainWindow(app_engine)
    window.show()

    exit_code = app.exec()

    # ------------------------------------------------------------------ #
    # 4. Shutdown Engine
    # ------------------------------------------------------------------ #
    app_engine.stop()
    sys.exit(exit_code)


# ------------------------------------------------------------------ #
# Private helpers — each owns exactly one bootstrap concern
# ------------------------------------------------------------------ #


def _install_exception_handler(app_engine) -> None:
    """Install a global Qt exception handler that logs and shows a dialog."""

    def _handler(exc_type, exc_value, exc_tb) -> None:
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))

        if hasattr(app_engine, "context") and hasattr(app_engine.context, "logger"):
            app_engine.context.logger.error(
                f"Uncaught UI Exception: {exc_value}\n{tb_str}"
            )
        else:
            print(f"Uncaught UI Exception:\n{tb_str}")

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("Critical System Error")
        msg.setText("An unexpected error occurred in the UI layer.")
        msg.setInformativeText(str(exc_value))
        msg.setDetailedText(tb_str)
        msg.exec()

    sys.excepthook = _handler


def _apply_font(app: QApplication, config: IConfig) -> None:
    """Apply the preferred monospace font read from config, with a safe fallback chain."""
    family = config.get(ConfigKeys.UI_FONT_FAMILY, "Consolas")
    size = config.get(ConfigKeys.UI_FONT_SIZE, 10, cast=int)
    fallbacks = config.get(ConfigKeys.UI_FONT_FALLBACKS, ["Consolas"])

    font = QFont(family, size)
    font.setStyleHint(QFont.Monospace)
    font.insertSubstitutions(family, fallbacks)
    app.setFont(font)


def _apply_theme(app: QApplication, config: IConfig) -> None:
    """Apply qdarktheme, replacing the default accent color with the one from config."""
    accent = config.get(ConfigKeys.UI_THEME_ACCENT_COLOR, "#F3BA2F")
    replace = config.get(
        ConfigKeys.UI_THEME_REPLACE_COLOR,
        "rgba(138.000, 180.000, 247.000, 1.000)",
    )

    raw = qdarktheme.load_stylesheet("dark")
    app.setStyleSheet(raw.replace(replace, accent))


if __name__ == "__main__":
    main()
