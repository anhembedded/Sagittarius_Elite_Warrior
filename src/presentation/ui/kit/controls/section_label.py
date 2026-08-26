"""
@brief `SectionLabel` — a small muted heading over a group of content.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from ..style import StyleRole
from .styled_label import StyledLabel


class SectionLabel(StyledLabel):
    """
    @brief A `StyledLabel` rendered as a group heading: muted, bold, letter-
    spaced, and uppercased.

    @details
    **The accent tick is opt-in and off by default.** Only one of the
    reference consumer's three headings has it; defaulting it on would give
    the other two a visual element they never had. When on, it is a QSS
    `border-left` rather than the consumer's child `QFrame` — see
    `StyleRole.SECTION_LABEL_TICKED` for the one recorded visual difference
    that follows from that.

    **It is a widget, and the version it replaces is a layout.** The
    consumer's `_SectionLabel` subclasses `QHBoxLayout`, so its four call
    sites read `addLayout(_SectionLabel("Actions"))`. Migrating them means
    `addWidget(...)` instead. That is a real edit at each site rather than a
    drop-in, and it is the price of the heading being a thing rather than an
    arrangement — a layout cannot be styled, hidden, or enabled.

    **Uppercasing happens here.** The consumer is inconsistent about it: one
    helper calls `.upper()` and is passed Title Case, two others are passed
    strings that are already uppercase. Doing it in the widget is idempotent
    for the latter and makes the heading's case a property of what it is
    rather than of how each caller happened to type it.
    """

    def __init__(
        self,
        text: str = "",
        *,
        tick: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            text.upper(),
            role=(StyleRole.SECTION_LABEL_TICKED if tick else StyleRole.SECTION_LABEL),
            parent=parent,
        )
        self._tick = tick

    @property
    def tick(self) -> bool:
        return self._tick

    def setText(self, text: str) -> None:
        """@brief Sets the heading, uppercased.

        @details Overrides `QLabel.setText` rather than adding a sibling
        method: a consumer holding this as a `QLabel` — which is what it is
        — would otherwise get a lowercase heading without knowing there was
        a rule."""
        super().setText(text.upper())
