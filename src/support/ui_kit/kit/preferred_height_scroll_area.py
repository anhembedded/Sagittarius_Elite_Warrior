"""A `QScrollArea` that scrolls its content instead of squashing it.

@par The mechanism, because it is not obvious and it cost a screen
`QScrollArea.setWidgetResizable(True)` resizes the content to the viewport and
only ever scrolls once the content's **minimum** height no longer fits. A
column of cards whose children can each shrink has a minimum far below the
height it actually wants, so Qt compresses it to fit and the scroll bar never
appears — the panel looks cramped rather than scrollable.

Measured on the real app at 1920x1080 (`BOT-129`): the Trading screen's rail
wants 1178px, was given 647px, and reported a minimum of 302px — so it was
squeezed by 531px with no scroll bar offered. Backtest looked like "the one
screen that scrolls" only because its content's minimum happens to be 1256px,
large enough that Qt had no room to compress it.

This class keeps the content's minimum height equal to the height it asks for,
so the same overflow produces a scroll bar on every screen instead of on the
one screen whose content refused to shrink.

@par Charts keep stretching — this does not pin them
`setWidgetResizable(True)` still stretches the content whenever the viewport is
taller than that minimum, and the content's own layout hands the extra space to
whatever is stretchy inside it. So a chart still grows into a tall window; what
it can no longer do is be compressed below the height it asked for.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QFrame, QScrollArea, QWidget

#: The two events after which the content's preferred height can differ from
#: what it was: a layout re-run (a row added, a card shown/hidden) and its own
#: resize (a width change re-wraps text, which changes the height it needs).
_RESYNC_EVENTS = frozenset({QEvent.Type.LayoutRequest, QEvent.Type.Resize})


class PreferredHeightScrollArea(QScrollArea):
    """@brief Vertical-only scroll area whose content is never compressed below
    the height it asks for.

    @details Pre-configured the way every screen already configured its own
    hand-rolled one: resizable, borderless, no horizontal scroll bar. Screens
    build one instead of a bare `QScrollArea` so the behaviour is identical
    everywhere rather than depending on how compressible each screen's content
    happens to be.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def setWidget(self, widget: QWidget) -> None:
        """Takes the content and starts tracking the height it asks for."""
        super().setWidget(widget)
        if widget is not None:
            widget.installEventFilter(self)
            self._resync_preferred_height()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Re-reads the content's preferred height after it re-lays-out.

        Watching rather than overriding `resizeEvent`: the height a column of
        cards wants changes when *its own* layout runs, which does not
        necessarily coincide with this scroll area being resized.
        """
        if watched is self.widget() and event.type() in _RESYNC_EVENTS:
            self._resync_preferred_height()
        return super().eventFilter(watched, event)

    def _resync_preferred_height(self) -> None:
        """Pins the content's minimum height to its `sizeHint()`.

        Guarded against re-entry by only writing when the value actually
        changes: `setMinimumHeight()` resizes the content, which delivers the
        `Resize` this same filter listens for. `sizeHint()` reads the content's
        layout and does not depend on the widget's own minimum, so one write
        settles it rather than ratcheting upward.
        """
        content = self.widget()
        if content is None:
            return
        preferred = content.sizeHint().height()
        if preferred > 0 and content.minimumHeight() != preferred:
            content.setMinimumHeight(preferred)
