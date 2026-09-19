"""Desktop-tier probe for `BUG-115` — does an embedded QML scene reach the
SCREEN with the surface colour behind it, not just `widget.grab()`?

Why this is a script and not a pytest: the defect only exists on the texture
rendering path of a real windowing session (xcb / wayland / windows). Under
`QT_QPA_PLATFORM=offscreen` — every pytest tier in this repo — Qt takes the
software path and the bug is invisible (`BUG-115` §2.4). This follows
`ci-rule.md` §3's Desktop E2E convention (`python_backtest_pan_desktop_e2e.py`):
opt-in, refuses to run headless, exits non-zero on a real failure.

Run on a desktop, or on Linux without one:

    PYTHONPATH=.. QT_QPA_PLATFORM=xcb xvfb-run -a -s "-screen 0 800x600x24" \\
        .venv/bin/python scripts/quick_surface_desktop_probe.py

Exit 0: the pixel in the scene's empty region equals the surface token on
the real screen. Exit 1: it does not (black on X11, see-through on Wayland).
Exit 2: refused — no real display.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

if os.environ.get("QT_QPA_PLATFORM") in {"offscreen", "minimal"}:
    sys.stderr.write(
        "Desktop probe needs a real windowing session — the software path under "
        f"{os.environ['QT_QPA_PLATFORM']!r} cannot show this defect (BUG-115 §2.4).\n"
    )
    sys.exit(2)

_SUPERPROJECT = Path(__file__).resolve().parent.parent.parent
if str(_SUPERPROJECT) not in sys.path:
    sys.path.insert(0, str(_SUPERPROJECT))

from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import QApplication
from Sagittarius_Elite_Warrior.src.support.ui_kit.embed import QuickSurface
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import (
    Panel,
    StyleRole,
    background_token,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.theme_bootstrap import (
    seed_app_theme,
)
from sagittarius_engine.extensions.pyside_mvc import get_theme_bridge

_WINDOW_SIZE = 300
_MARGIN = 30
_SETTLE_SECONDS = 1.5
#: A pixel inside the scene, outside the one red square it paints.
_EMPTY_POINT = (150, 150)
_RED_POINT = (_MARGIN + 30, _MARGIN + 30)
_QML = """
import QtQuick
Item {
    Rectangle { x: 20; y: 20; width: 40; height: 40; color: "red" }
}
"""


def _settle(app: QApplication) -> None:
    deadline = time.monotonic() + _SETTLE_SECONDS
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)


def main() -> int:
    app = QApplication(sys.argv)
    seed_app_theme()

    with tempfile.TemporaryDirectory() as tmp:
        qml_file = Path(tmp) / "Probe.qml"
        qml_file.write_text(_QML, encoding="utf-8")

        panel = Panel()
        panel.body_layout.setContentsMargins(_MARGIN, _MARGIN, _MARGIN, _MARGIN)
        surface = QuickSurface(qml_file, surface=StyleRole.SURFACE)
        panel.body_layout.addWidget(surface, 1)
        panel.resize(_WINDOW_SIZE, _WINDOW_SIZE)
        panel.show()
        _settle(app)

        expected = QColor(
            str(get_theme_bridge().value(background_token(StyleRole.SURFACE)))
        )
        screen = QGuiApplication.primaryScreen().grabWindow(panel.winId()).toImage()
        grab = panel.grab().toImage()

    on_screen = QColor(screen.pixel(*_EMPTY_POINT))
    in_grab = QColor(grab.pixel(*_EMPTY_POINT))
    red_on_screen = QColor(screen.pixel(*_RED_POINT))
    print(
        f"platform={QGuiApplication.platformName()} expected={expected.name()} "
        f"screen={on_screen.name()} grab={in_grab.name()} red={red_on_screen.name()}"
    )
    if red_on_screen.name() != "#ff0000":
        print(
            "FAIL: the scene itself did not reach the screen — probe is not looking at it"
        )
        return 1
    if on_screen.rgb() != expected.rgb():
        print(
            "FAIL: empty QML region on the real screen is not the surface token (BUG-115)"
        )
        return 1
    print("OK: embedded QML scene is opaque with the surface token, on the real screen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
