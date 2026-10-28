"""`EPIC-047E` - calls something once, the first time a widget is shown.

The VPS tab's presenter is built at application start with every mode's, but its link must start only when the person opens
the tab (a run that never opens it makes no connection).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QWidget


class FirstShown(QObject):
    def __init__(self, widget: QWidget, then: Callable[[], None]) -> None:
        super().__init__(widget)
        self._then = then
        self._done = False
        widget.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt's name
        if not self._done and event.type() == QEvent.Type.Show:
            self._done = True
            self._then()
        return False
