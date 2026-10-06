"""Pictures of the booted workbench, one per mode and window size, for a
reviewer to judge what no check measures (`pr-review` SKILL §5.1).

The conformance suite proves the rule's measurable half: stock controls, a
fitting window, every command in a menu. Whether a mode reads well (what
is likely is visible, the order of the panels, a crowded toolbar, a blank
centre) is judged by looking. These are the same window the suite measures
(the real `MainWindow` over seeded, network-free fakes), drawn by
`QWidget.grab()`, so they need no display and run headless in CI.

Extension cases, each a local change here: a mode with one of its menus
open (`QMenu.grab()` beside the window); a dialog a command opens; a mode
in a second state (a result drawn, a run going), named `route~state@WxH`;
a dark palette, once the app follows one.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QMainWindow

#: The environment variable that names where the pictures go; unset, a test
#: writes them to its own temporary directory.
SCREENSHOT_DIR_ENV = "SEW_UI_SCREENSHOTS"

#: Fewer distinct colours than this, over a sampled grid, is a blank picture
#: (one flat background with maybe a frame), not a drawn mode.
_MIN_COLOURS = 8
_SAMPLE_STEP = 16


def screenshot_name(route: str, size: QSize) -> str:
    return f"{route}@{size.width()}x{size.height()}.png"


def capture_modes(
    window: QMainWindow,
    navigate: Callable[[str], object],
    size: QSize,
    out_dir: Path,
) -> list[Path]:
    """Shows each navigable mode at `size` and saves the whole window."""
    out_dir.mkdir(parents=True, exist_ok=True)
    window.resize(size)
    window.show()
    saved = []
    for route in window.navigation.modes():
        navigate(route)
        for _ in range(3):
            QApplication.processEvents()
        path = out_dir / screenshot_name(route, size)
        if not window.grab().save(str(path)):
            raise OSError(f"could not write {path}")
        saved.append(path)
    return saved


def distinct_colours(image: QImage) -> int:
    """How many colours a grid of samples over `image` holds."""
    return len(
        {
            image.pixel(x, y)
            for x in range(0, image.width(), _SAMPLE_STEP)
            for y in range(0, image.height(), _SAMPLE_STEP)
        }
    )


def is_blank(image: QImage) -> bool:
    return image.isNull() or distinct_colours(image) < _MIN_COLOURS
