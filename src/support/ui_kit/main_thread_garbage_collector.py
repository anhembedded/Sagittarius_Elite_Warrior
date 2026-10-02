"""`BUG-140` — the app's cyclic garbage collection, on the Qt main thread.

`main_thread_collection.py` holds the policy and says why. This is the app's
scheduler for it: a timer owned by the `QApplication`, so it fires on the main
thread while the event loop runs.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QTimer
from Sagittarius_Elite_Warrior.src.support.ui_kit.main_thread_collection import (
    collect_due_generations,
    stop_automatic_collection,
)

logger = logging.getLogger("App.UiKit.GarbageCollector")

#: pyqtgraph's interval. A due check is three integer comparisons, so a short
#: interval costs nothing and keeps collections as small as automatic ones.
_INTERVAL_MS = 100


class MainThreadGarbageCollector(QObject):
    """Collects due generations every `_INTERVAL_MS` on the main thread.

    No `stop()`: automatic collection stays off until the process exits,
    because turning it back on while a worker thread lives is the hazard.
    """

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self.setObjectName("mainThreadGarbageCollector")
        self._timer = QTimer(self)
        self._timer.setInterval(_INTERVAL_MS)
        self._timer.timeout.connect(collect_due_generations)

    def start(self) -> None:
        stop_automatic_collection()
        self._timer.start()
        logger.info(
            "[gc-policy] automatic collection off; the main thread collects "
            "due generations every %d ms (BUG-140)",
            _INTERVAL_MS,
        )
