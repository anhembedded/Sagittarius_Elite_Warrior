"""`EPIC-043C` — an item view's cell takes a tone's colour from its own data.

A table built over a `RowTableModel` says what a cell means with the model's `_tone` hook. A tree
or a list built over a `QStandardItemModel` (the Plan dock's property table and checks) has no such
hook, so a cell says it in `TONE_ROLE` and this delegate — the Engine's, writing the text as the
Engine does — paints it in the meaning table's colour on the application's palette, asked at each
paint so a change of the colour scheme is followed and High Contrast keeps the platform's colours.

Extension cases: another view with toned cells is one `setItemDelegate` with this class; another
role to colour (a selected cell's text) is one more line in `initStyleOption`.

Capability: Colour an item view's cell by meaning from its own data (TONE_ROLE)
    Also: tone role, cell colour, tree view colour, QStandardItemModel colour, delegate
    Use: ToneKindDelegate, TONE_ROLE
    User: src/modules/bots/ui/bots_screen/row_kind_delegate.py
    Status: stable
"""

from __future__ import annotations

from typing import override

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QGuiApplication, QPalette
from PySide6.QtWidgets import QStyleOptionViewItem
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    Tone,
    tone_colour,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import KindDelegate

#: The item data role a cell answers with its `Tone`.
TONE_ROLE = int(Qt.ItemDataRole.UserRole) + 20


class ToneKindDelegate(KindDelegate):
    """The Engine's delegate, painting a cell's text in the colour of the tone it names."""

    @override
    def initStyleOption(
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> None:
        super().initStyleOption(option, index)
        tone = index.data(TONE_ROLE)
        if not isinstance(tone, Tone):
            return
        colour = tone_colour(tone, QGuiApplication.palette())
        if colour is not None:
            option.palette.setColor(QPalette.ColorRole.Text, colour)
