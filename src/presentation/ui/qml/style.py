"""`ensure_qml_style()` — pin Qt Quick Controls to a style that honours tokens.

@par Why this exists as its own module
Originally private to `QmlOverlay` (`host.py`), and correct there for as long
as `QmlOverlay` was the only shape a QML modal could take. `EPIC-015`'s
`SymbolPicker.qml` needs the exact same pin but cannot go through
`QmlOverlay` — its `Popup` draws its own header/search/footer, so wrapping it
in `Overlay`'s title/subtitle/footer-button chrome would duplicate what the
`.qml` already renders (`.agents/rules/qml-rule.md` §0.1's second host shape).
Two real hosts needing one pure, stateless pin is exactly the case
`qml-rule.md` §0.2 names: dùng chung, không viết bản sao — so it moved here
rather than being copied a second time.
"""

from __future__ import annotations

from PySide6.QtQuickControls2 import QQuickStyle

_STYLE_NAME = "Basic"


def ensure_qml_style() -> None:
    """Pins Qt Quick Controls to a style that honours `background:` overrides.

    @details The platform default on Windows is the native style, which
    **silently ignores** `background:`/`contentItem:` and renders native
    chrome instead, logging only a warning. Call this before any QML loads —
    including from tests, which never run the app bootstrapper, so a test
    cannot pass against chrome the user would never see.
    """
    if QQuickStyle.name() != _STYLE_NAME:
        QQuickStyle.setStyle(_STYLE_NAME)
