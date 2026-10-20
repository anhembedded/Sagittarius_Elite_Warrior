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
in a second state (a result drawn, a run going), named `route~state@WxH`.

The dark scheme is a second state of every mode, named `route~dark@WxH` (`EPIC-043A`):
`apply_scheme` asks Qt for it with `QStyleHints.setColorScheme`, the call Tools →
Options makes; where the platform theme ignores the request (Qt's offscreen and Linux
platforms do, measured under PySide6 6.11.1), the picture is drawn with a standard dark
`QPalette` laid on the application, so a frame is never silently light. A test lays
that palette; the app itself never writes one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPalette
from PySide6.QtWidgets import QApplication, QMainWindow

#: The environment variable that names where the pictures go; unset, a test
#: writes them to its own temporary directory.
SCREENSHOT_DIR_ENV = "SEW_UI_SCREENSHOTS"

#: Fewer distinct colours than this is a blank picture (one flat background
#: with maybe a frame), not a drawn mode.
_MIN_COLOURS = 8
#: The picture is shrunk to this width, smoothly, before its colours are
#: counted, so every pixel is read at once and a thin line of text (an empty
#: view's instruction) still shows as the greys it blurs into.
_SAMPLE_WIDTH = 240


@dataclass(frozen=True)
class Screenshot:
    """One mode's picture, and its centre drawn alone: the window's frame
    (menu bar, mode bar, status bar) holds enough colours by itself to make
    a blank mode look drawn (review of PR #372)."""

    route: str
    path: Path
    centre: QImage


#: The two schemes a frame is drawn in; "light" is whatever the platform draws by default.
SCHEMES = ("light", "dark")

_DARK_ROLES = {
    QPalette.ColorRole.Window: "#2b2b2b",
    QPalette.ColorRole.WindowText: "#e8e8e8",
    QPalette.ColorRole.Base: "#1e1e1e",
    QPalette.ColorRole.AlternateBase: "#272727",
    QPalette.ColorRole.Text: "#e8e8e8",
    QPalette.ColorRole.Button: "#353535",
    QPalette.ColorRole.ButtonText: "#e8e8e8",
    QPalette.ColorRole.ToolTipBase: "#353535",
    QPalette.ColorRole.ToolTipText: "#e8e8e8",
    QPalette.ColorRole.PlaceholderText: "#8a8a8a",
    QPalette.ColorRole.Highlight: "#2a6fc4",
    QPalette.ColorRole.HighlightedText: "#ffffff",
    QPalette.ColorRole.Link: "#5aa0f0",
    QPalette.ColorRole.BrightText: "#ffffff",
}


def _dark_palette() -> QPalette:
    palette = QPalette()
    for role, name in _DARK_ROLES.items():
        palette.setColor(role, QColor(name))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#7a7a7a"))
    return palette


@dataclass(frozen=True)
class AppliedScheme:
    """What `apply_scheme` did, so a frame says how it was drawn."""

    scheme: str
    #: Whether Qt itself switched (`QStyleHints.colorScheme()` now reads the scheme).
    honoured_by_qt: bool
    #: Whether a standard dark palette stands in for the platform's own.
    palette_laid: bool


def apply_scheme(app: QApplication, scheme: str) -> AppliedScheme:
    """Switches the running application to `scheme` the way Options → Apply will,
    and reports whether Qt did it or the stand-in palette had to."""
    hints = app.styleHints()
    if scheme == "light":
        hints.unsetColorScheme()
        app.setPalette(app.style().standardPalette())
        return AppliedScheme("light", honoured_by_qt=True, palette_laid=False)
    hints.setColorScheme(Qt.ColorScheme.Dark)
    app.processEvents()
    if hints.colorScheme() == Qt.ColorScheme.Dark:
        return AppliedScheme("dark", honoured_by_qt=True, palette_laid=False)
    QGuiApplication.setPalette(_dark_palette())
    app.processEvents()
    return AppliedScheme("dark", honoured_by_qt=False, palette_laid=True)


def restore_scheme(app: QApplication) -> None:
    """Back to what the platform draws, for the next test."""
    apply_scheme(app, "light")


def screenshot_name(route: str, size: QSize, scheme: str = "light") -> str:
    state = "" if scheme == "light" else f"~{scheme}"
    return f"{route}{state}@{size.width()}x{size.height()}.png"


def capture_modes(
    window: QMainWindow,
    navigate: Callable[[str], object],
    size: QSize,
    out_dir: Path,
    scheme: str = "light",
) -> list[Screenshot]:
    """Shows each navigable mode at `size` and saves the whole window."""
    out_dir.mkdir(parents=True, exist_ok=True)
    window.resize(size)
    window.show()
    saved = []
    for route in window.navigation.modes():
        navigate(route)
        for _ in range(3):
            QApplication.processEvents()
        path = out_dir / screenshot_name(route, size, scheme)
        if not window.grab().save(str(path)):
            raise OSError(f"could not write {path}")
        centre = window.hosts[route].centralWidget()
        saved.append(Screenshot(route, path, centre.grab().toImage()))
    return saved


def distinct_colours(image: QImage) -> int:
    """How many colours `image` holds, shrunk to `_SAMPLE_WIDTH`."""
    small = image.scaledToWidth(
        _SAMPLE_WIDTH, Qt.TransformationMode.SmoothTransformation
    )
    return len(
        {small.pixel(x, y) for x in range(small.width()) for y in range(small.height())}
    )


def is_blank(image: QImage) -> bool:
    return image.isNull() or distinct_colours(image) < _MIN_COLOURS
