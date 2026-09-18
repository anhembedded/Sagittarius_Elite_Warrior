"""Backtest engine limitations notice — a read-only list, and that is why it is
the one of `SelectList.qml`'s four hosts that did **not** become a picker.

`EPIC-015` §4c had rendered this through `SelectListVM(selectable=False)`, on the
argument that a read-only bullet list is a picker "with nothing to click". True
of the `.qml` delegate, and the wrong shape for QtWidgets: `kit.PickerOverlay`'s
whole contract is that a row can be chosen and emits its value, so serving this
screen from it would mean a flag that turns off the component's only promise.
`EPIC-025` PR 4.3e therefore splits the two apart — the three real pickers go to
`PickerOverlay`, this one to what HLD §11.3 calls a read-only summary: an
`Overlay` holding wrapped text, one bullet per caveat.

One consumer, so it is built here rather than promoted into `kit/` — `base_feed`'s
rule: a shape becomes shared when the *second* consumer for it appears.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import Overlay

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel

_TITLE = "LIMITATIONS OF THIS RUN"
_BULLET = "•"
_EMPTY_TEXT = "This run reported no limitations."


class LimitationsDialog(Overlay):
    """
    @brief Plain-text caveats for the run that just finished — nothing here is
    clickable.
    """

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        self._vm = view_model
        super().__init__(_TITLE, parent=parent)
        self.setObjectName("limitationsPopup")
        self.resize(480, 420)

        self._list_host = QWidget()
        self._list_layout = QVBoxLayout(self._list_host)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(self._list_host)
        self.body_layout.addWidget(self._scroll, 1)

        view_model.run_result.limitationsChanged.connect(self.refresh)
        self.refresh()

    def showEvent(self, event) -> None:
        self.refresh()
        super().showEvent(event)

    def refresh(self) -> None:
        """Rebuilds the list from the run's current caveats.

        Rebuilt rather than appended to: the previous run's caveats are not
        this run's, and the widget is constructed once and reused.
        """
        while self._list_layout.count():
            entry = self._list_layout.takeAt(0)
            if entry is None:  # pragma: no cover — count() > 0 guarantees one
                break
            widget = entry.widget()
            if widget is not None:
                # Detached before `deleteLater()`, not only taken out of the
                # layout. Taking the item leaves the label parented to the
                # host, and a deferred delete is delivered by the main event
                # loop rather than by the call that scheduled it — so between
                # the two, the host still holds the previous run's labels.
                # Written without this line first, and the "replaces the
                # previous run" test read both runs' caveats at once.
                widget.setParent(None)
                widget.deleteLater()

        limitations = list(self._vm.run_result.limitations)
        for index, text in enumerate(limitations):
            self._list_layout.addWidget(self._bullet_row(index, text))
        if not limitations:
            self._list_layout.addWidget(self._bullet_row(0, _EMPTY_TEXT, bullet=""))

    @staticmethod
    def _bullet_row(index: int, text: str, *, bullet: str = _BULLET) -> QLabel:
        """One wrapped line. A `QLabel` rather than a two-widget row, because
        the bullet belongs to the same wrapped paragraph as its text — laid out
        as two widgets it would hang at the top of a three-line caveat."""
        label = QLabel(f"{bullet} {text}".strip())
        label.setObjectName(f"lblLimitation_{index}")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label
