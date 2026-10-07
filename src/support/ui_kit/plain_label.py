"""The one way UI code makes a `QLabel`: its text is text, never markup.

A `QLabel` defaults to `Qt.AutoText`, which renders any string that merely
looks like HTML as rich text. A label that shows an exception's message, a
symbol from a catalog or a file name therefore shows whatever an exchange or a
file chose to send: on 2026-10-07 the Bots panel drew a gateway's
`502 Bad Gateway` page as a heading (`BUG-168`). Every label is made here, so
text is text unless a file says otherwise in the guard's exemption table
(`tests/unit/architecture/test_labels_show_plain_text.py`).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget


def plain_label(text: str = "", parent: QWidget | None = None) -> QLabel:
    """A `QLabel` showing `text` exactly as written."""
    label = QLabel(text, parent)
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label
