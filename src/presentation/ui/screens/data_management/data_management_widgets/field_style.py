"""The one stylesheet the Data Management input fields share."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
)


def field_style(extra_height: int | None = None) -> str:
    """QSS matching `FieldBackground.qml`: STATE_IDLE_BG fill, BORDER outline,
    6px radius. `extra_height` overrides the default 32px min-height (the
    search box uses 26px, matching `FieldBackground { implicitHeight: 26 }`)."""
    height = extra_height if extra_height is not None else 32
    return (
        f"background-color: {Palette.STATE_IDLE_BG}; color: {Palette.TEXT_PRIMARY}; "
        f"border: 1px solid {Palette.BORDER}; border-radius: 6px; "
        f"min-height: {height}px; padding: 0 6px;"
    )
