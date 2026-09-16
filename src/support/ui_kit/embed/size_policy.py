"""`QuickSizePolicy` — how an embedded QML scene and its widget agree on size.

Names the two `QQuickWidget.ResizeMode` values by what a host actually wants
from them, so a host declares an intent (`FILL` / `HUG`) instead of a Qt
enum whose direction ("root object to view" or "view to root object") every
reader has to work out again.
"""

from __future__ import annotations

from enum import Enum

from PySide6.QtQuickWidgets import QQuickWidget


class QuickSizePolicy(Enum):
    """@brief Who follows whom when the widget and the QML root disagree."""

    #: The QML root stretches to whatever size the QtWidgets layout gives the
    #: widget — a panel body, a modal body, a table. The default, and what
    #: every host but one wants.
    FILL = QQuickWidget.ResizeMode.SizeRootObjectToView
    #: The widget shrinks to the QML root's own implicit size — a compact
    #: pill row that must not stretch across a header. `ChartToolbar` is the
    #: one host today.
    HUG = QQuickWidget.ResizeMode.SizeViewToRootObject
