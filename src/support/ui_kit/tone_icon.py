"""`EPIC-043C` — a Lucide icon in a tone's colour on the application's palette.

The icon files carry `currentColor`, and `IconLoader` fills it with the colour it is given. A state's
icon is given the colour of its tone, asked of the palette at the time (so a change of colour scheme
is followed by whoever asks again), or the palette's own text colour when the tone has none
(`NEUTRAL`, and High Contrast, where the platform keeps its colours).

Capability: A Lucide icon coloured by meaning (profit, loss, warning), for a state's badge
    Also: state icon, status icon, tinted icon, icon colour, tone icon
    Use: tone_icon
    User: src/support/ui_kit/state_badge.py
    Status: stable
"""

from __future__ import annotations

from PySide6.QtGui import QGuiApplication, QIcon, QPalette
from Sagittarius_Elite_Warrior.src.support.ui_kit.assets.icon_loader import (
    get_icon_loader,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    Tone,
    tone_colour,
)


def tone_icon(name: str, tone: Tone, size: int) -> QIcon:
    """The icon `name`, `size` pixels square, in `tone`'s colour."""
    palette = QGuiApplication.palette()
    colour = tone_colour(tone, palette) or palette.color(QPalette.ColorRole.WindowText)
    return get_icon_loader().get_icon(name, colour.name(), size)
