"""Standalone live preview for the SymbolPicker QML component."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.embed import QuickSurface
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.interfaces.i_symbol_picker_source import (
    ISymbolPickerSource,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.SymbolPicker.symbol_picker_theme import (
    SymbolPickerTheme,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.SymbolPicker.symbol_picker_vm import (
    SymbolPickerVM,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import StyleRole

_QML_FILE = Path(__file__).with_name("SymbolPicker.qml")


class _PreviewSource(ISymbolPickerSource):
    """Small deterministic source used only by the live preview harness."""

    _SYMBOLS = (
        "ETHUSDT",
        "ETHBTC",
        "ETHEUR",
        "AAVEETH",
        "ADAETH",
        "ARBETH",
        "BNBETH",
        "ETHARS",
        "ETHBRL",
        "ETHFDUSD",
        "ETHFITRY",
        "ETHIDR",
        "ETHJPY",
        "ETHMXN",
    )

    def get_symbols(self) -> Sequence[str]:
        return self._SYMBOLS

    def get_favourites(self) -> Sequence[str]:
        return ("ETHBTC", "ETHUSDT")

    def get_recents(self) -> Sequence[str]:
        return ("ETHEUR", "ETHFDUSD")

    def get_current(self) -> str:
        return "ETHUSDT"

    def set_favourite(self, symbol: str, favourite: bool) -> None:
        pass


def build_preview() -> QWidget:
    """Build the SymbolPicker without an app modal or application ViewModel."""
    vm = SymbolPickerVM(_PreviewSource())
    vm.refresh()
    theme = SymbolPickerTheme()
    # This component reads its own `theme` object, not the shared `Theme`
    # bridge (see `symbol_picker_theme.py` for why) — both are context
    # properties `QuickSurface` keeps alive for the scene's lifetime.
    surface = QuickSurface(
        _QML_FILE,
        surface=StyleRole.SURFACE,
        context={"symbolPickerPreviewVM": vm, "symbolPickerPreviewTheme": theme},
        object_name="symbolPickerPreview",
    )
    root = surface.root_object
    root.setProperty("vm", vm)
    root.setProperty("theme", theme)
    root.openPicker()
    surface.resize(720, 620)
    return surface
