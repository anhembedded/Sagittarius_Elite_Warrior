"""The mode's Live stream menu command, checked while a chart connects or is live.

A chart tells the action what its state says (`mirror`); only the user checking
or unchecking it reaches the chart's `on_user_toggled`, never the chart's own
update, which would otherwise start or stop the stream it just reported.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction


class LiveStreamAction:
    """@brief A checkable "Live stream" command that mirrors a chart's state."""

    def __init__(
        self, on_user_toggled: Callable[[bool], None], parent: QObject
    ) -> None:
        self.action = QAction("&Live stream", parent)
        self.action.setCheckable(True)
        self._on_user_toggled = on_user_toggled
        self._mirroring = False
        self.action.toggled.connect(self._on_toggled)

    def mirror(self, streaming: bool) -> None:
        """Shows the chart's state without reporting it as the user's choice."""
        self._mirroring = True
        self.action.setChecked(streaming)
        self._mirroring = False

    def _on_toggled(self, checked: bool) -> None:
        if not self._mirroring:
            self._on_user_toggled(checked)
