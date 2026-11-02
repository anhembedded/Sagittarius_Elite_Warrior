"""`EPIC-047E` — stops the VPS link when the application quits.

@details Qt-free callers (the headless boot) never import this: `SharedVpsSession` reaches it through a `Deferred` when it builds
the session, which happens only in a run that has a window.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QCoreApplication


def stop_at_quit(stop: Callable[[], None]) -> None:
    app = QCoreApplication.instance()
    if app is not None:
        app.aboutToQuit.connect(stop)
