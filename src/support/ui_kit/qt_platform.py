"""Shared Qt platform detection — one place to answer "is there a real
display session behind this app, or is Qt running headless".

Extracted from `chart_card/plot_layout.py` (its original, sole owner) once
`app_bootstrapper.py`'s exception handler became a second real consumer
(`BUG-048`) — not speculative: both call sites need the same answer for the
same reason, a UI element that only makes sense with a human able to see and
interact with it must behave differently when there is no such human.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

#: Platform plugin names PySide6 reports when there is no real display session
#: for a human to interact with. `offscreen` is what this project's own tests
#: and CI run under (`QT_QPA_PLATFORM=offscreen`); `minimal`/`minimalegl` are
#: the same idea on platforms/backends that use those names instead.
_HEADLESS_QT_PLATFORMS = frozenset({"offscreen", "minimal", "minimalegl"})


def qt_platform_name() -> str:
    """The running `QApplication`'s platform plugin name, lowercased — the
    empty string if no `QApplication` exists yet."""
    app = QApplication.instance()
    # `platformName()` is on `QGuiApplication` at runtime, but
    # `QCoreApplication.instance()` is typed as returning the base class, and
    # PySide6's stubs do not narrow it. A local ignore rather than a path
    # excluded from the gate: the gap is one attribute on one line, and this
    # file only left the wholesale `presentation/` exclusion in `EPIC-025`
    # PR 1.6f.
    return app.platformName().lower() if app is not None else ""  # type: ignore[attr-defined]


def is_headless_qt_platform() -> bool:
    """True when Qt is running under a platform with no real display session
    — no window manager, no user, nothing that can dismiss a modal dialog."""
    return qt_platform_name() in _HEADLESS_QT_PLATFORMS
