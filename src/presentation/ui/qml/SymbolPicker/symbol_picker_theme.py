"""Theme contract and default tokens for the standalone symbol picker."""

from __future__ import annotations

from PySide6.QtCore import Property, QObject


class SymbolPickerTheme(QObject):
    """Default visual tokens supplied by the component itself.

    A host may inject another QObject exposing the same property names under
    the QML context name ``Theme`` without importing any application palette.

    The values below are copied from ``assets/palette.py``'s ``Palette``
    (this app's real single source of truth for colour), not derived from
    it: importing ``Palette`` here would pull in ``assets/__init__.py``'s
    engine-backed asset validation, which is exactly the app dependency this
    standalone component exists to avoid (see ``NOTES.md``). Because the
    two are copies rather than one value read twice, they can drift —
    ``tests/unit/presentation/ui/qml/test_symbol_picker_theme_matches_palette.py``
    is what catches that instead, so a `Palette` change that is not mirrored
    here fails a test rather than silently going stale in this preview.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

    @Property(str, constant=True)
    def bg(self) -> str:
        return "#0a0a0c"  # token-exempt: mirrors Palette, see NOTES.md

    @Property(str, constant=True)
    def bgCard(self) -> str:
        return "#111318"  # token-exempt: mirrors Palette, see NOTES.md

    @Property(str, constant=True)
    def bgCardHeader(self) -> str:
        return "#15171d"  # token-exempt: mirrors Palette, see NOTES.md

    @Property(str, constant=True)
    def border(self) -> str:
        return "#23262e"  # token-exempt: mirrors Palette, see NOTES.md

    @Property(str, constant=True)
    def textPrimary(self) -> str:
        return "#e8e9ec"  # token-exempt: mirrors Palette, see NOTES.md

    @Property(str, constant=True)
    def accent(self) -> str:
        return "#f3ba2f"  # token-exempt: mirrors Palette, see NOTES.md

    @Property(str, constant=True)
    def muted(self) -> str:
        return "#848e9c"  # token-exempt: mirrors Palette, see NOTES.md

    @Property(str, constant=True)
    def stateIdleBg(self) -> str:
        return "#17181d"  # token-exempt: mirrors Palette, see NOTES.md

    @Property(str, constant=True)
    def stateHoverBg(self) -> str:
        return "#1f2127"  # token-exempt: mirrors Palette, see NOTES.md

    @Property(str, constant=True)
    def stateActiveTint(self) -> str:
        return "#1ff3ba2f"  # token-exempt: mirrors Palette, see NOTES.md

    @Property(str, constant=True)
    def stateNavBorder(self) -> str:
        return "#2a2d36"  # token-exempt: mirrors Palette, see NOTES.md
