"""
@brief `StyledCheckBox` — a `QCheckBox` with token-styled label text.
"""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QWidget

from ..style import StyleRole, apply_role


class StyledCheckBox(QCheckBox):
    """A `QCheckBox` styled for readable label text on this app's dark
    surfaces — Qt's own indicator box is left native, not reskinned; no
    consumer of the QML `StyledCheck` this replaces needed a custom
    indicator glyph, so this doesn't build one speculatively."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        apply_role(self, StyleRole.CHECKBOX)
