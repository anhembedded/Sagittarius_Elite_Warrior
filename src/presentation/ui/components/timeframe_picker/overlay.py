"""`TimeframePickerOverlay` — choose a candle interval. Shared by every screen.

Replaces Backtest's `TimeframePickerDialog`: a flat 4-column grid of five
hand-styled cells reading `1m`, `5m`, `15m`, `1h`, `1d`. Two things were wrong
with it, and only one of them was cosmetic.

The cosmetic one: a bare code in a box says nothing. `12h` and `1d` and `3d`
sit next to each other with no indication which is which unit, and a user
scanning for "four hours" reads sixteen strings rather than four sections.

The one that mattered: the five codes were `DEFAULT_TIMEFRAMES`, a tuple that
exists to size a *chart toolbar* row. `TimeFrame` has always declared sixteen,
the exchange serves all sixteen, and the database stores all sixteen — the
picker was the only thing in the stack that could not reach eleven of them.
The catalogue this reads is derived from `TimeFrame` itself, so that gap
cannot reopen.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...kit import Overlay, StyleRole, apply_role
from .catalogue import (
    GROUP_LABELS,
    TimeframeOption,
    group_options,
    options_for,
)
from .timeframe_card import TimeframeCard

_TITLE = "CHỌN KHUNG THỜI GIAN"
_EMPTY_TEXT = "Không có khung thời gian nào khả dụng."
_KEY_HINTS = "↑↓ di chuyển   ↵ chọn"
_CURRENT_TEXT = "Đang dùng: {code}"
_HIGH_RESOLUTION_WARNING = (
    "Khung dưới 1 phút sinh rất nhiều nến — một ngày dữ liệu ở 1s là ~86.400 nến."
)

#: Four to a row: codes are two or three characters, and four columns keeps
#: the longest group (phút — five members) to two tidy rows.
_COLUMNS = 4


class TimeframePickerOverlay(Overlay):
    """
    @brief A modal, grouped grid of candle intervals.

    @details Choosing emits `timeframe_chosen` and closes. Sections come from
    the catalogue rather than from this widget, so a timeframe added to
    `TimeFrame` lands in the right section with no edit here.

    Deliberately not searchable, unlike `SymbolPickerOverlay`: sixteen cells
    fit on screen at once, and a search box over a list the user can already
    see whole is one more thing to skip past.
    """

    timeframe_chosen = Signal(str)

    def __init__(
        self,
        get_options: Callable[[], Sequence[str]],
        get_current: Callable[[], str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(_TITLE, parent=parent)
        self.setObjectName("timeframePickerModal")
        self.resize(520, 520)

        self._get_options = get_options
        self._get_current = get_current
        self._cards: list[TimeframeCard] = []
        self._focused_index = -1

        self._build_results_area()
        self._build_footer_row()

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #

    def _build_results_area(self) -> None:
        self._status_label = QLabel(_EMPTY_TEXT)
        self._status_label.setObjectName("lblTimeframeStatus")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        apply_role(self._status_label, StyleRole.CAPTION)
        self.body_layout.addWidget(self._status_label)

        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(14)
        self._content_layout.addStretch(1)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setWidget(content)
        apply_role(self._scroll, StyleRole.LIST_SURFACE)
        self.body_layout.addWidget(self._scroll, 1)

    def _build_footer_row(self) -> None:
        self._warning_label = QLabel(_HIGH_RESOLUTION_WARNING)
        self._warning_label.setObjectName("lblTimeframeWarning")
        self._warning_label.setWordWrap(True)
        apply_role(self._warning_label, StyleRole.CAPTION)
        self.body_layout.addWidget(self._warning_label)

        row = QHBoxLayout()
        hints = QLabel(_KEY_HINTS)
        hints.setObjectName("lblTimeframeKeyHints")
        apply_role(hints, StyleRole.CAPTION)
        row.addWidget(hints)
        row.addStretch(1)
        self._current_label = QLabel()
        self._current_label.setObjectName("lblTimeframeCurrent")
        apply_role(self._current_label, StyleRole.CAPTION)
        row.addWidget(self._current_label)
        self.body_layout.addLayout(row)

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #

    def showEvent(self, event) -> None:
        """Re-reads the option list and the current choice on every open.

        A screen can narrow its offered timeframes at runtime (Data
        Management's coverage view does), and the current one changes between
        opens, so neither can be captured at construction.
        """
        self.refresh()
        super().showEvent(event)

    def refresh(self) -> None:
        """Re-reads the source data and re-renders. Public for a screen whose
        option list changes while the dialog is already built."""
        self._clear_content()
        options = options_for(list(self._get_options()))
        current = self._get_current()

        self._current_label.setText(_CURRENT_TEXT.format(code=current or "—"))
        if not options:
            self._status_label.setVisible(True)
            self._scroll.setVisible(False)
            self._warning_label.setVisible(False)
            return

        self._status_label.setVisible(False)
        self._scroll.setVisible(True)
        # Shown only when a sub-minute timeframe is actually on offer — a
        # standing warning about a choice the screen does not present is
        # noise the user learns to ignore.
        self._warning_label.setVisible(
            any(option.is_high_resolution for option in options)
        )

        for group, members in group_options(options):
            self._content_layout.addWidget(self._section_heading(GROUP_LABELS[group]))
            self._content_layout.addLayout(self._build_grid(members, current))
        self._content_layout.addStretch(1)

    def _build_grid(self, options: list[TimeframeOption], current: str) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(8)
        for index, option in enumerate(options):
            card = TimeframeCard(option, is_current=option.code == current)
            card.clicked.connect(lambda code=option.code: self._choose(code))
            grid.addWidget(card, index // _COLUMNS, index % _COLUMNS)
            self._cards.append(card)
        return grid

    def _clear_content(self) -> None:
        self._cards = []
        self._focused_index = -1
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item is None:  # pragma: no cover - count() > 0 guarantees one
                break
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
                continue
            child = item.layout()
            if child is not None:
                self._delete_layout(child)

    @staticmethod
    def _delete_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item is None:  # pragma: no cover - count() > 0 guarantees one
                break
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        layout.deleteLater()

    @staticmethod
    def _section_heading(text: str) -> QLabel:
        label = QLabel(text)
        apply_role(label, StyleRole.SECTION_LABEL)
        return label

    # ------------------------------------------------------------------ #
    # Interaction
    # ------------------------------------------------------------------ #

    def _choose(self, code: str) -> None:
        self.timeframe_chosen.emit(code)
        self.accept()

    def keyPressEvent(self, event) -> None:
        """Arrow keys move a highlight, Enter chooses it — the same contract
        `SymbolPickerOverlay` offers, so the two pickers do not need learning
        separately."""
        key = event.key()
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Up) and self._cards:
            self._move_focus(1 if key == Qt.Key.Key_Down else -1)
            event.accept()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self._cards:
            index = max(self._focused_index, 0)
            self._choose(self._cards[index].option.code)
            event.accept()
            return
        super().keyPressEvent(event)

    def _move_focus(self, step: int) -> None:
        self._focused_index = (self._focused_index + step) % len(self._cards)
        for index, card in enumerate(self._cards):
            card.selected = index == self._focused_index
        self._scroll.ensureWidgetVisible(self._cards[self._focused_index])
