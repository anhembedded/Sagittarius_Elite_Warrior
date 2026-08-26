"""
@brief `AppProgressBar` — a muted status caption over engine's
`StyledProgressBar`.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    StyledProgressBar,
    StyleRole,
    apply_role,
)

_CAPTION_SPACING = 4
#: The bar is a thin rule, not a control you read a number off — which is
#: also why the percentage stays hidden (see below).
_BAR_HEIGHT = 10


class AppProgressBar(
    QWidget
):  # base-exempt: a caption stacked over a bar, not a surface
    """
    @brief The two-part progress widget this app actually uses: a caption
    line, and a bar under it.

    @details
    **Engine ships the bar, not this.** `EPIC-007C` looked at the one real
    instance of this shape and found it was a composite — a column — rather
    than a leaf control, and recorded it as belonging on the app side. This
    is that composite, now that `EPIC-007E` needs it to exist somewhere both
    the Backtest and Data Management screens can reach.

    **The caption does the work.** All three call sites in this app set
    `set_status_text` and nothing else; not one has ever called `set_value`
    or `set_range`. So the bar spends its life in indeterminate mode as a
    "something is happening" rule, and the caption is what the user reads.

    **The percentage stays hidden.** The version this replaces set
    `setTextVisible(True)` on a bar it also fixed to 10px tall, with a 10px
    font inside a 1px border — text with nowhere to go. Nobody noticed
    because nobody ever set a value for it to render. Engine's
    `StyledProgressBar` defaults it off; that default is kept rather than
    re-enabling a thing that never worked.

    `set_indeterminate(False)` now restores the range the bar had before,
    where the old version made it a deliberate no-op to avoid clobbering a
    range set separately. Same protection, without the trap that turning
    busy mode off silently did nothing.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_CAPTION_SPACING)

        self._status_label = QLabel()
        apply_role(self._status_label, StyleRole.CAPTION)
        self._status_label.setVisible(False)
        layout.addWidget(self._status_label)

        self._bar = StyledProgressBar()
        self._bar.setObjectName("progressBar")
        self._bar.setFixedHeight(_BAR_HEIGHT)
        layout.addWidget(self._bar)

    @property
    def status_text(self) -> str:
        return self._status_label.text()

    def set_status_text(self, text: str) -> None:
        """@brief Sets the caption, hiding it when empty so an idle bar does
        not carry a blank line above it."""
        self._status_label.setText(text)
        self._status_label.setVisible(bool(text))

    def set_range(self, minimum: int, maximum: int) -> None:
        self._bar.setRange(minimum, maximum)

    def set_value(self, value: int) -> None:
        self._bar.setValue(value)

    def set_indeterminate(self, indeterminate: bool) -> None:
        self._bar.set_indeterminate(indeterminate)
