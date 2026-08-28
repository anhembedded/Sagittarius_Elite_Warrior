"""One interval in the picker's grid: its exchange code and what it means."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from ...kit import SelectableCard, StyleRole, apply_role
from .catalogue import TimeframeOption

_CURRENT_TEXT = "Đang dùng"

_CARD_HEIGHT = 52


class TimeframeCard(SelectableCard):
    """
    @brief One candle interval: `4h` over `4 giờ`.

    @details The second line is the whole reason this is a card and not the
    bare cell it replaces. `12h`, `1d` and `3d` are three characters each and
    differ in the character that carries the unit — the position the eye
    reads last. Spelling the duration out is what makes the grid scannable,
    and it is also where "Đang dùng" goes, so the current choice is stated
    rather than left to a border colour alone.
    """

    def __init__(
        self,
        option: TimeframeOption,
        is_current: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._option = option
        self.setObjectName(f"timeframeCard_{option.code}")
        self.setFixedHeight(_CARD_HEIGHT)
        self.selected = is_current

        self.body_layout.setSpacing(2)
        code_label = QLabel(option.code)
        code_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        apply_role(code_label, StyleRole.TABLE_CELL_STRONG)
        self.body_layout.addWidget(code_label)

        status_label = QLabel(_CURRENT_TEXT if is_current else option.label)
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        apply_role(status_label, StyleRole.CAPTION)
        self.body_layout.addWidget(status_label)

    @property
    def option(self) -> TimeframeOption:
        """What this card renders — read by the dialog's keyboard navigation,
        so it never has to parse the code back out of a label."""
        return self._option
