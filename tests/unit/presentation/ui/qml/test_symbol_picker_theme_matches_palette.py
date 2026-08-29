"""Guard: `SymbolPickerTheme`'s standalone-preview colours must not silently
drift from `Palette`, this app's real single source of truth for colour.

`SymbolPickerTheme` cannot import `Palette` directly — `SymbolPicker` is
deliberately app-neutral (see its `NOTES.md`), and `Palette` lives behind
`assets/__init__.py`, which pulls in engine-backed asset validation this
standalone component must not depend on. So the two copies are kept in sync
by this test instead of by import.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.assets.palette import Palette
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.SymbolPicker.symbol_picker_theme import (
    SymbolPickerTheme,
)

#: Every token `SymbolPickerTheme` declares. Kept as an explicit list rather
#: than introspecting the class so a newly-added token cannot skip this
#: check by accident — extending the list is one line, and forgetting to is
#: the failure mode this test exists to catch in the first place.
_SHARED_TOKENS: tuple[str, ...] = (
    "bg",
    "bgCard",
    "bgCardHeader",
    "border",
    "textPrimary",
    "accent",
    "muted",
    "stateIdleBg",
    "stateHoverBg",
    "stateActiveTint",
    "stateNavBorder",
)


def test_symbol_picker_theme_matches_palette_for_every_shared_token():
    theme = SymbolPickerTheme()
    palette = Palette.as_ui_dict()

    mismatched = [
        token
        for token in _SHARED_TOKENS
        if str(getattr(theme, token)).lower() != str(palette[token]).lower()
    ]
    assert not mismatched, (
        "SymbolPickerTheme drifted from Palette for: "
        f"{mismatched} — update symbol_picker_theme.py to match Palette."
    )
